"""
API endpoints for finding trains and routes.
"""
import asyncio
import datetime
import logging
import time
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, Request

from api.models import TrainSummary, Route, RouteConstraints, StationStop, RouteLeg, AvailabilityResult
from cache.redis_client import (
    cache_client,
    TRAINS_BETWEEN_TTL, TRAINS_BETWEEN_PERM_TTL,
    TRAIN_SCHEDULE_PERM_TTL,
    AVAILABILITY_TTL,
)
from scraper.ntes_scraper import get_trains_between_stations, get_train_schedule as fetch_train_schedule
from core.graph import RouteGraph
from core.filters import get_candidate_stations
from core.geo import get_geo_indexer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Trains & Routes"])

async def get_schedule_cached(train_number: str, date: str, source: Optional[str] = None) -> List[StationStop]:
    """
    Fetch train schedule with a permanent (date-independent) Redis cache.
    A train's stops and timings don't change day-to-day, so we key on
    (train_number, source) only and cache for 30 days.
    """
    perm_key = f"schedule_perm:{train_number}:{source}"
    cached = await cache_client.get(perm_key)
    if cached:
        return [StationStop(**s) for s in cached]
    schedule = await fetch_train_schedule(train_number, date=date, source=source)
    if schedule:
        await cache_client.set(perm_key, [s.dict() for s in schedule], TRAIN_SCHEDULE_PERM_TTL)
    return schedule


async def get_trains_cached(source: str, destination: str, date: str) -> List[TrainSummary]:
    """
    Two-tier cache for trains between a station pair.

    Tier 1 — exact key (24 h): guards duplicate calls within the same session/day.
    Tier 2 — permanent key (30 days): date-independent; which trains run between
              two stations doesn't change. Day-of-week filtering is done locally
              using the stored days_of_run field so the right trains surface.
    """
    exact_key = f"trains_between:{source}:{destination}:{date}"
    cached_exact = await cache_client.get(exact_key)
    if cached_exact:
        return [TrainSummary(**t) for t in cached_exact]

    perm_key = f"trains_between_perm:{source}:{destination}"
    perm_data = await cache_client.get(perm_key)
    if perm_data:
        day_name = datetime.date.fromisoformat(date).strftime("%a").upper()
        day_filtered = [t for t in perm_data if day_name in (t.get("days_of_run") or [])]
        if day_filtered:
            logger.info(
                f"[Cache-Perm] {source}->{destination} on {day_name}: "
                f"{len(day_filtered)}/{len(perm_data)} trains (no IRCTC call)"
            )
            # Warm the exact key too so same-day repeated calls skip tier-2 lookup
            await cache_client.set(exact_key, day_filtered, TRAINS_BETWEEN_TTL)
            return [TrainSummary(**t) for t in day_filtered]

    # Live IRCTC call
    trains = await get_trains_between_stations(source, destination, date)
    if trains:
        trains_dicts = [t.dict() for t in trains]
        await cache_client.set(exact_key, trains_dicts, TRAINS_BETWEEN_TTL)
        # Merge into permanent cache so we accumulate all trains seen for this pair
        existing_nums = {t.get("train_number") for t in (perm_data or [])}
        new_entries = [t for t in trains_dicts if t.get("train_number") not in existing_nums]
        if new_entries or not perm_data:
            merged = (perm_data or []) + new_entries
            await cache_client.set(perm_key, merged, TRAINS_BETWEEN_PERM_TTL)

    return [TrainSummary(**t.dict()) for t in trains]

@router.get("/trains", response_model=List[TrainSummary])
async def get_trains(
    source: str = Query(..., description="Source station code", example="NDLS"),
    destination: str = Query(..., description="Destination station code", example="LKO"),
    date: datetime.date = Query(..., description="Date of journey", example="2024-11-25"),
    nearby_radius: float = Query(0.0, description="Include stations within X km radius")
):
    date_str = date.strftime("%Y-%m-%d")
    
    # Get direct trains
    results = await get_trains_cached(source, destination, date_str)
    
    # Expand to nearby if requested
    if nearby_radius > 0:
        geo = get_geo_indexer()
        nearby_sources = geo.get_nearby_stations(source, nearby_radius)
        nearby_dests = geo.get_nearby_stations(destination, nearby_radius)
        
        tasks = []
        # Trains from nearby sources to dest
        for s in nearby_sources:
            tasks.append(get_trains_cached(s, destination, date_str))
        # Trains from source to nearby dests
        for d in nearby_dests:
            tasks.append(get_trains_cached(source, d, date_str))
            
        extra_results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in extra_results:
            if isinstance(res, list):
                results.extend(res)
                
    # Unique results - Use string keys to preserve leading zeros
    unique = {f"{t.train_number}_{t.source_station}_{t.destination_station}": t for t in results}.values()
    return list(unique)

async def try_simplify_route(route: Route, source: str) -> Optional[Route]:
    """
    Detect the boarding-point trick: if a multi-leg route's second train also stops
    at the journey source BEFORE its ticketed boarding point, emit a single-leg route
    where the user books from the connection point but boards at their origin.

    Example: JP->DPA (Train A) + DPA->NAC (Train B), and Train B stops at JP before DPA.
    Result: 1-leg route — Train B, ticket DPA->NAC, board at JP.
    """
    if len(route.legs) < 2:
        return None

    second_leg = route.legs[1]

    try:
        # Fetch schedule starting from source. If source is a stop on this train
        # before second_leg.from_station, the response will include both in order.
        schedule = await get_schedule_cached(second_leg.train_number, second_leg.date, source=source)
        if not schedule:
            return None

        source_idx = next((i for i, s in enumerate(schedule) if s.station_code == source), -1)
        from_idx = next((i for i, s in enumerate(schedule) if s.station_code == second_leg.from_station), -1)

        # Source must appear in the schedule AND come before the ticketed boarding point
        if source_idx == -1 or from_idx == -1 or source_idx >= from_idx:
            return None

        simplified_leg = second_leg.copy()
        simplified_leg.from_station = source                           # display/route origin: JP
        simplified_leg.booked_from_station = second_leg.from_station   # ticket says: DPA
        simplified_leg.actual_boarding_station = source                # board at: JP

        # Update departure/arrival times and duration using schedule stop data
        board_stop = schedule[source_idx]
        dest_stop = next((s for s in schedule if s.station_code == second_leg.to_station), None)
        try:
            if board_stop.departure_time and dest_stop and dest_stop.arrival_time:
                dep_h, dep_m = map(int, board_stop.departure_time.split(":")[:2])
                arr_h, arr_m = map(int, dest_stop.arrival_time.split(":")[:2])
                base = datetime.datetime.strptime(second_leg.date, "%Y-%m-%d")
                dep_dt = base.replace(hour=dep_h, minute=dep_m, second=0, microsecond=0)
                arr_dt = base.replace(hour=arr_h, minute=arr_m, second=0, microsecond=0)
                if arr_dt <= dep_dt:
                    arr_dt += datetime.timedelta(days=1)
                simplified_leg.departure_time = dep_dt
                simplified_leg.arrival_time = arr_dt
                simplified_leg.duration_minutes = int((arr_dt - dep_dt).total_seconds() / 60)
        except Exception:
            pass  # Fall back to original DPA-based times

        logger.info(
            f"✨ [Simplifier] {source}->{second_leg.to_station}: "
            f"board Train {second_leg.train_number} at {source}, ticket from {second_leg.from_station}"
        )

        return Route(
            legs=[simplified_leg],
            total_duration_minutes=simplified_leg.duration_minutes,
            total_distance_km=0,
            connections=0,
            is_fully_confirmed=True,
        )
    except Exception as e:
        logger.warning(f"Route simplification check failed for {second_leg.train_number}: {e}")
        return None


@router.get("/routes", response_model=List[Route])
async def get_routes(
    request: Request,
    source: str = Query(..., description="Source station code", example="NDLS"),
    destination: str = Query(..., description="Destination station code", example="LKO"),
    date: datetime.date = Query(..., description="Date of journey", example="2024-11-25"),
    max_duration_hours: float = Query(48.0),
    max_connections: int = Query(3),
    min_layover_mins: int = Query(30, description="Minimum layover in minutes"),
    max_layover_mins: int = Query(240),
    classes: str = Query(""),
    departure_after: str = Query("00:00"),
    departure_before: str = Query("23:59"),
    arrival_before: str = Query("23:59"),
    only_confirmed: bool = Query(False),
    nearby_radius: float = Query(0.0, description="Include stations within X km radius"),
    quota: str = Query("GN", description="Quota code (e.g. GN, TQ)")
):
    preferred_classes = classes.split(",") if classes else []
    
    constraints = RouteConstraints(
        max_total_duration_hours=max_duration_hours,
        max_connections=max_connections,
        min_layover_minutes=min_layover_mins,
        max_layover_minutes=max_layover_mins,
        preferred_classes=preferred_classes,
        departure_after=departure_after,
        departure_before=departure_before,
        arrival_before=arrival_before,
        only_confirmed=only_confirmed
    )

    # Step 1: Get all direct trains (including nearby)
    # --- END-TO-END PERFORMANCE TIMER START ---
    search_start_time = time.perf_counter()
    logger.info(f"Search: {source} -> {destination} on {date}")
    date_str = date.strftime("%Y-%m-%d")
    direct_trains = await get_trains(source, destination, date, nearby_radius)
    
    # Get all potential start/end stations for the graph
    start_stations = [source]
    end_stations = [destination]
    if nearby_radius > 0:
        geo = get_geo_indexer()
        start_stations.extend(geo.get_nearby_stations(source, nearby_radius))
        end_stations.extend(geo.get_nearby_stations(destination, nearby_radius))
    
    # Step 2: Get candidate intermediate stations (geographically on the way)
    intermediate_stations = get_candidate_stations(source, destination)
    
    # Step 3: Fan out leg fetches in batches to control concurrency
    logger.debug(f"Fanning out via {len(intermediate_stations)} junctions (Batch size: 3)...")
    tasks = []
    for s in start_stations:
        for mid in intermediate_stations:
            tasks.append(get_trains_cached(s, mid, date_str))
    
    for mid in intermediate_stations:
        for e in end_stations:
            tasks.append(get_trains_cached(mid, e, date_str))

    # Batch processing to prevent connection pool exhaustion
    results = []
    batch_size = 3
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        batch_results = await asyncio.gather(*batch, return_exceptions=True)
        results.extend(batch_results)
    
    all_trains = list(direct_trains)
    for res in results:
        if isinstance(res, list):
            all_trains.extend(res)
            
    # Remove duplicates
    unique_trains_dict = {f"{t.train_number}_{t.source_station}_{t.destination_station}": t for t in all_trains}
    unique_trains = unique_trains_dict.values()
    logger.debug(f"Unique trains for graph: {len(unique_trains_dict)}")

    # Build a map from train_number -> class_list for use in availability checking.
    # A train may appear as multiple source/dest pairs; any non-empty class_list wins.
    train_class_map: dict = {}
    for t in unique_trains:
        if t.class_list:
            train_class_map[t.train_number] = t.class_list

    # Step 4: Build graph and find valid routes for all combinations of start/end
    graph = RouteGraph()
    graph.build_graph(list(unique_trains))
    
    all_discovered_routes = []
    # We use a set to avoid searching the same start-end pair if nearby expansion found the same codes
    processed_pairs = set()
    
    for s in start_stations:
        for e in end_stations:
            if (s, e) in processed_pairs: continue
            discovered = graph.find_routes(s, e, constraints, date_str)
            all_discovered_routes.extend(discovered)
            processed_pairs.add((s, e))
    
    routes = all_discovered_routes
    logger.debug(f"Discovered {len(routes)} routes.")
    irctc_scraper = request.app.state.irctc_scraper
    
    # 1. Identify all unique legs
    unique_legs_map = {} # (train, from, to, date) -> leg_data
    for route in routes:
        for leg in route.legs:
            key = (leg.train_number, leg.from_station, leg.to_station, leg.date)
            if key not in unique_legs_map:
                unique_legs_map[key] = leg



    _ALL_CLASSES = ["SL", "3A", "3E", "2A", "1A", "CC", "EC", "2S"]
    # How many seconds before TTL expiry we proactively refresh in the background.
    _STALE_REFRESH_THRESHOLD = 60

    async def fetch_one(train_number: str, from_stn: str, to_stn: str, date: str, cls: str, quota_code: str):
        """
        Fetch availability for a single class with three layers of protection:

        1. Fast read  — return cached value immediately if present.
        2. Stale-while-revalidate — if cache is about to expire (< 60s), serve the
           stale value NOW and schedule a background refresh so the NEXT caller gets
           a fresh value without waiting.
        3. Distributed lock — if the cache is cold, only ONE worker across all
           instances fires the IRCTC call (double-checked locking). Everyone else
           waits up to 15 s for that worker to populate the cache, then reads it.
        """
        cache_key = f"avail:{train_number}:{from_stn}:{to_stn}:{date}:{cls}:{quota_code}"

        # ── Layer 1 & 2: cache hit ──────────────────────────────────────────────
        cached = await cache_client.get(cache_key)
        if cached:
            ttl = await cache_client.get_ttl(cache_key)
            if 0 < ttl < _STALE_REFRESH_THRESHOLD:
                # Serve stale value now; refresh in background so next caller gets fresh data.
                asyncio.create_task(_background_refresh(train_number, from_stn, to_stn, date, cls, quota_code, cache_key))
            return cached

        # ── Layer 3: distributed lock — prevents stampede ──────────────────────
        async with cache_client.lock(cache_key) as acquired:
            if not acquired:
                # Redis unavailable — fall through to a direct call (degraded mode)
                pass
            else:
                # Double-check: another worker may have filled the cache while we waited
                cached = await cache_client.get(cache_key)
                if cached:
                    return cached

            # We hold the lock (or Redis is down) — acquire a global rate-limit token
            # before hitting IRCTC so the total call rate across all instances stays
            # within IRCTC's tolerance.
            token_granted = await cache_client.acquire_irctc_token()
            if not token_granted:
                # Rate limit exhausted — return None; caller handles degradation
                return None

            try:
                avail = await irctc_scraper.get_seat_availability(
                    train_number, from_stn, to_stn, date, cls, quota=quota_code
                )
                if avail:
                    avail_dict = avail.dict() if hasattr(avail, "dict") else avail
                    await cache_client.set(cache_key, avail_dict, AVAILABILITY_TTL)
                    return avail_dict
            except Exception as e:
                logger.warning(f"Could not fetch class {cls} for train {train_number}: {e}")
        return None

    async def _background_refresh(train_number: str, from_stn: str, to_stn: str, date: str, cls: str, quota_code: str, cache_key: str):
        """Silently refresh a near-expiry availability key without blocking any caller."""
        lock_key = f"refresh:{cache_key}"
        async with cache_client.lock(lock_key, timeout=20, blocking_timeout=0) as acquired:
            if not acquired:
                return  # Another worker is already refreshing this key
            try:
                avail = await irctc_scraper.get_seat_availability(
                    train_number, from_stn, to_stn, date, cls, quota=quota_code
                )
                if avail:
                    await cache_client.set(cache_key, avail.dict(), AVAILABILITY_TTL)
                    logger.debug(f"[BG-Refresh] {train_number}/{cls} refreshed silently")
            except Exception as e:
                    logger.debug(f"[BG-Refresh] {train_number}/{cls} failed: {e}")

    async def _fetch_availability(leg, quota_code: str):
        # Use the train's own class list if we have it; otherwise fall back to all classes.
        classes_to_check = train_class_map.get(leg.train_number) or _ALL_CLASSES
        results = await asyncio.gather(*[
            fetch_one(leg.train_number, leg.from_station, leg.to_station, leg.date, c, quota_code)
            for c in classes_to_check
        ])
        return [AvailabilityResult(**r) if isinstance(r, dict) else r for r in results if r]

    # 2. Fetch all unique availabilities in batches
    unique_keys = list(unique_legs_map.keys())
    avail_results = []
    batch_size = 3
    
    for i in range(0, len(unique_keys), batch_size):
        batch_keys = unique_keys[i:i+batch_size]
        batch_tasks = [_fetch_availability(unique_legs_map[k], quota) for k in batch_keys]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        avail_results.extend(batch_results)
    
    avail_lookup = {}
    for key, result in zip(unique_keys, avail_results):
        if not isinstance(result, Exception) and result:
            # Ensure we store objects, not raw dicts, to satisfy Pydantic
            avail_lookup[key] = [AvailabilityResult(**r) if isinstance(r, dict) else r for r in result]
        else:
            avail_lookup[key] = []

    # 2.5 Boarding Point Optimization Helper
    async def try_optimize_boarding(leg: RouteLeg) -> List[AvailabilityResult]:
        """Try to find seats by booking from a previous station in parallel."""
        try:
            schedule = await get_schedule_cached(leg.train_number, leg.date, source=leg.from_station)
            source_idx = next((i for i, s in enumerate(schedule) if s.station_code == leg.from_station), -1)
            
            if source_idx > 0:
                # Check up to 2 previous stations in parallel
                prev_indices = range(source_idx - 1, max(-1, source_idx - 3), -1)
                
                async def check_prev_station(idx):
                    prev_stn = schedule[idx].station_code
                    logger.info(f"🧠 [Optimizer] Parallel check: {leg.train_number} from {prev_stn}")
                    results = await _fetch_availability(RouteLeg(
                        train_number=leg.train_number,
                        train_name=leg.train_name,
                        from_station=prev_stn,
                        to_station=leg.to_station,
                        date=leg.date,
                        departure_time=leg.departure_time,
                        arrival_time=leg.arrival_time,
                        duration_minutes=leg.duration_minutes
                    ), quota)
                    
                    if any(str(getattr(r, 'status', r.get('status', '') if isinstance(r, dict) else '')).upper() == "AVAILABLE" for r in results):
                        return (prev_stn, results)
                    return None

                backtrack_results = await asyncio.gather(*[check_prev_station(idx) for idx in prev_indices])
                
                # Pick the first one that has seats
                for res in backtrack_results:
                    if res:
                        prev_stn, alt_results = res
                        logger.debug(f"[Optimizer] Seats found booking from {prev_stn}")
                        leg.booked_from_station = prev_stn
                        leg.actual_boarding_station = leg.from_station
                        return alt_results
        except Exception as e:
            logger.warning(f"Boarding optimization failed for {leg.train_number}: {e}")
        return []

    # 3. Assign and Filter
    final_confirmed = []

    def get_status(res):
        if hasattr(res, 'status'): return str(res.status).upper()
        if isinstance(res, dict): return str(res.get('status', '')).upper()
        return str(res).upper()

    def is_valid_status(res):
        st = get_status(res)
        valid_prefixes = ["AVAILABLE", "CURR_AVBL"]
        return any(st == v or st.startswith(v) for v in valid_prefixes) and st != "NOT_AVAILABLE"

    def leg_train_has_service(results):
        """True if at least one class returned a non-NOT_AVAILABLE status (WL, RAC, AVAILABLE)."""
        return any(get_status(r) != "NOT_AVAILABLE" for r in results)

    for original_route in routes:
        route_confirmed = True
        route_availability_unknown = False
        new_legs = []

        route_is_unusable = False
        for original_leg in original_route.legs:
            leg = original_leg.copy()
            key = (leg.train_number, leg.from_station, leg.to_station, leg.date)
            leg_results = avail_lookup.get(key, [])

            # Check if this leg has ANY service at all (Available, WL, or RAC)
            # If leg_results is empty (error/rate limit), we assume it might have service to be safe
            if leg_results and not leg_train_has_service(leg_results):
                logger.debug(f"🚫 [Filter] Discarding route: {leg.train_number} has no service on {leg.date}")
                route_is_unusable = True
                break

            leg_has_seats = any(is_valid_status(r) for r in leg_results)

            # Empty results = rate-limited or network error (not "no seats").
            if not leg_results:
                route_availability_unknown = True
                leg.availability = []
                new_legs.append(leg)
                continue

            # Train runs this leg — try boarding optimizer if no confirmed seats yet.
            if not leg_has_seats:
                optimized_results = await try_optimize_boarding(leg)
                if optimized_results:
                    leg_results = optimized_results
                    leg_has_seats = True

            leg.availability = leg_results

            # Train runs but only WL/RAC — keep the route, mark as unconfirmed.
            if not leg_has_seats:
                route_confirmed = False

            new_legs.append(leg)

        if route_is_unusable or not new_legs:
            continue

        route = original_route.copy()
        route.legs = new_legs
        route.is_fully_confirmed = route_confirmed and not route_availability_unknown
        final_confirmed.append(route)

    # Step 6: Boarding-point simplification
    # For each confirmed multi-leg route, check if the second train also stops at
    # the user's origin before the connection point — and if so, produce a cleaner
    # single-leg alternative with a "book from X, board at Y" tip.
    logger.info("Step 6: Checking for boarding-point simplification opportunities...")
    simplified = []
    for route in final_confirmed:
        if route.connections > 0:
            simp = await try_simplify_route(route, source)
            if simp:
                simplified.append(simp)

    # Avoid duplicating a simplified route if the same train already appeared as a
    # confirmed direct option (would mean JP->NAC direct was confirmed, very unlikely
    # given the premise, but guard anyway).
    direct_keys = {
        (r.legs[0].train_number, r.legs[-1].to_station)
        for r in final_confirmed if r.connections == 0
    }
    novel_simplified = [
        r for r in simplified
        if (r.legs[0].train_number, r.legs[-1].to_station) not in direct_keys
    ]
    all_routes = final_confirmed + novel_simplified
    # Sort: Confirmed first, then by number of connections, then duration.
    # Take top 20 to keep the UI clean but meaningful.
    final_routes = sorted(
        all_routes, 
        key=lambda x: (not x.is_fully_confirmed, x.connections, x.total_duration_minutes)
    )[:20]

    total_search_duration = time.perf_counter() - search_start_time
    logger.info(f"Search complete in {total_search_duration:.2f}s — {len(final_routes)} routes found")
    
    return final_routes

@router.get("/{train_number}/schedule", response_model=List[StationStop])
async def get_train_schedule(
    train_number: str,
    date: Optional[str] = Query(None, description="Journey date in YYYY-MM-DD"),
    source: Optional[str] = Query(None, description="Starting station code")
):
    """Get the full itinerary and station stops for a specific train."""
    # Delegates to the shared permanent-cache helper so both the route pipeline
    # and this public endpoint read/write the same Redis key.
    try:
        schedule = await get_schedule_cached(train_number, date or datetime.date.today().isoformat(), source=source)
        if not schedule:
            raise HTTPException(status_code=404, detail=f"Schedule for train {train_number} not found.")
        return schedule
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching schedule for {train_number}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve train schedule.")
