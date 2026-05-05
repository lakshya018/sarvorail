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
from core import cache
from scraper.ntes_scraper import get_trains_between_stations, get_train_schedule as fetch_train_schedule
from core.graph import RouteGraph
from core.filters import get_candidate_stations
from core.geo import get_geo_indexer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Trains & Routes"])

_ALL_CLASSES = ["SL", "3A", "3E", "2A", "1A", "CC", "EC", "2S"]


async def get_schedule_cached(train_number: str, date: str, source: Optional[str] = None) -> List[StationStop]:
    """Fetch train schedule with in-memory cache."""
    perm_key = f"schedule_perm:{train_number}:{source}"
    cached = cache.get(perm_key)
    if cached:
        return [StationStop(**s) for s in cached]
    schedule = await fetch_train_schedule(train_number, date=date, source=source)
    if schedule:
        cache.set(perm_key, [s.dict() for s in schedule], cache.TRAIN_SCHEDULE_PERM_TTL)
    return schedule


async def get_trains_cached(source: str, destination: str, date: str) -> List[TrainSummary]:
    """Fetch trains between stations with in-memory cache."""
    cache_key = f"trains_direct:{source}:{destination}:{date}"
    cached = cache.get(cache_key)
    if cached:
        return [TrainSummary(**t) for t in cached]

    trains = await get_trains_between_stations(source, destination, date)
    summaries = [TrainSummary(**t.dict()) for t in trains]
    if summaries:
        cache.set(cache_key, [s.dict() for s in summaries], cache.TRAINS_BETWEEN_TTL)
    return summaries


@router.get("/trains", response_model=List[TrainSummary])
async def get_trains(
    source: str = Query(..., description="Source station code", examples=["NDLS"]),
    destination: str = Query(..., description="Destination station code", examples=["LKO"]),
    date: datetime.date = Query(..., description="Date of journey", examples=["2024-11-25"]),
):
    return await get_trains_cached(source, destination, date.strftime("%Y-%m-%d"))


async def try_simplify_route(route: Route, source: str) -> Optional[Route]:
    """
    Boarding-point trick: if a multi-leg route's second train also stops at the
    journey source BEFORE its ticketed boarding point, emit a single-leg route
    where the user books from the connection point but boards at their origin.
    """
    if len(route.legs) < 2:
        return None

    second_leg = route.legs[1]

    try:
        schedule = await get_schedule_cached(second_leg.train_number, second_leg.date, source=source)
        if not schedule:
            return None

        source_idx = next((i for i, s in enumerate(schedule) if s.station_code == source), -1)
        from_idx = next((i for i, s in enumerate(schedule) if s.station_code == second_leg.from_station), -1)

        if source_idx == -1 or from_idx == -1 or source_idx >= from_idx:
            return None

        simplified_leg = second_leg.copy()
        simplified_leg.from_station = source
        simplified_leg.booked_from_station = second_leg.from_station
        simplified_leg.actual_boarding_station = source

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
            pass

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


def _get_status(res):
    if hasattr(res, 'status'): return str(res.status).upper()
    if isinstance(res, dict): return str(res.get('status', '')).upper()
    return ''


def _is_available(res):
    st = _get_status(res)
    return ("AVAILABLE" in st or "CURR_AVBL" in st or "AVBL" in st) and "NOT" not in st


@router.get("/routes", response_model=List[Route])
async def get_routes(
    request: Request,
    source: str = Query(..., description="Source station code", examples=["NDLS"]),
    destination: str = Query(..., description="Destination station code", examples=["LKO"]),
    date: datetime.date = Query(..., description="Date of journey", examples=["2024-11-25"]),
    max_duration_hours: float = Query(48.0),
    max_connections: int = Query(3),
    min_layover_mins: int = Query(30),
    max_layover_mins: int = Query(240),
    classes: str = Query(""),
    departure_after: str = Query("00:00"),
    departure_before: str = Query("23:59"),
    arrival_before: str = Query("23:59"),
    only_confirmed: bool = Query(False),
    quota: str = Query("GN")
):
    search_start_time = time.perf_counter()
    date_str = date.strftime("%Y-%m-%d")

    if not source or not destination:
        return []

    full_cache_key = f"routes_full:{source}:{destination}:{date_str}:{quota}"
    cached_routes = cache.get(full_cache_key)
    if cached_routes:
        logger.info(f"✨ [Cache Hit] {source}->{destination}")
        return [Route(**r) if isinstance(r, dict) else r for r in cached_routes]

    irctc_scraper = request.app.state.irctc_scraper

    constraints = RouteConstraints(
        max_total_duration_hours=max_duration_hours,
        max_connections=max_connections,
        min_layover_minutes=min_layover_mins,
        max_layover_minutes=max_layover_mins,
        preferred_classes=classes.split(",") if classes else [],
        departure_after=departure_after,
        departure_before=departure_before,
        arrival_before=arrival_before,
        only_confirmed=only_confirmed
    )

    # ── Helpers used by both direct and multi-leg flows ───────────────────────

    async def fetch_one(train_number, from_stn, to_stn, date, cls, quota_code):
        cache_key = f"avail:{train_number}:{from_stn}:{to_stn}:{date}:{cls}:{quota_code}"
        cached = cache.get(cache_key)
        if cached: return cached
        try:
            avail = await irctc_scraper.get_seat_availability(train_number, from_stn, to_stn, date, cls, quota=quota_code)
            if avail:
                avail_dict = avail.dict()
                cache.set(cache_key, avail_dict, cache.AVAILABILITY_TTL)
                return avail_dict
        except Exception as e:
            logger.debug(f"fetch_one error {train_number}/{cls}: {e}")
        return None

    async def fetch_leg_availability(leg, train_class_map, quota_code: str):
        classes_to_check = train_class_map.get(leg.train_number) or _ALL_CLASSES
        tasks = [fetch_one(leg.train_number, leg.from_station, leg.to_station, leg.date, c, quota_code) for c in classes_to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [AvailabilityResult(**r) if isinstance(r, dict) else r for r in results if isinstance(r, dict)]

    def assemble_routes(routes, avail_lookup):
        """Attach availability to legs and mark route as fully confirmed if all legs have seats."""
        out = []
        for route in routes:
            new_legs = []
            all_have_seats = True
            for leg in route.legs:
                leg_copy = leg.copy()
                key = (leg.train_number, leg.from_station, leg.to_station, leg.date)
                leg_results = avail_lookup.get(key, [])
                leg_copy.availability = leg_results
                if not any(_is_available(r) for r in leg_results):
                    all_have_seats = False
                new_legs.append(leg_copy)
            r = route.copy()
            r.legs = new_legs
            r.is_fully_confirmed = all_have_seats
            out.append(r)
        return out

    # ── Step 1: Try DIRECT trains first ───────────────────────────────────────
    logger.info(f"Step 1: Fetching direct trains {source}->{destination}")
    direct_trains = await get_trains_cached(source, destination, date_str)
    train_class_map = {t.train_number: t.class_list for t in direct_trains if t.class_list}

    direct_routes = []
    if direct_trains:
        graph = RouteGraph()
        graph.build_graph(direct_trains)
        direct_routes = graph.find_routes(source, destination, constraints, date_str)
        # Keep only single-leg (direct) routes
        direct_routes = [r for r in direct_routes if r.connections == 0]

    # Fetch availability for direct routes in parallel
    direct_legs_map = {}
    for r in direct_routes:
        for leg in r.legs:
            key = (leg.train_number, leg.from_station, leg.to_station, leg.date)
            if key not in direct_legs_map:
                direct_legs_map[key] = leg

    if direct_legs_map:
        direct_keys = list(direct_legs_map.keys())
        direct_results = await asyncio.gather(
            *[fetch_leg_availability(direct_legs_map[k], train_class_map, quota) for k in direct_keys],
            return_exceptions=True
        )
        direct_avail_lookup = {
            k: (r if isinstance(r, list) else [])
            for k, r in zip(direct_keys, direct_results)
        }
    else:
        direct_avail_lookup = {}

    direct_assembled = assemble_routes(direct_routes, direct_avail_lookup)
    direct_with_seats = [r for r in direct_assembled if r.is_fully_confirmed]

    # ── Decision: if direct trains have seats, return ONLY direct trains ──────
    if direct_with_seats:
        logger.info(f"✅ Found {len(direct_with_seats)} direct trains with seats. Skipping multi-leg search.")
        final_routes = sorted(direct_assembled, key=lambda x: x.total_duration_minutes)[:20]
        cache.set(full_cache_key, [r.dict() for r in final_routes], ttl_seconds=86400)
        duration_ms = (time.perf_counter() - search_start_time) * 1000
        logger.info(f"Search completed in {duration_ms:.0f}ms. Returning {len(final_routes)} direct routes.")
        return final_routes

    # ── Step 2: No direct trains with seats — expand to multi-leg routes ──────
    logger.info(f"⚠️  No direct trains with seats. Expanding to multi-leg search via intermediate junctions...")

    intermediate_stations = get_candidate_stations(source, destination)
    logger.info(f"Step 2: {len(intermediate_stations)} candidate junctions identified")

    # Fan out source→junction and junction→destination parallel calls
    leg_tasks = []
    for mid in intermediate_stations:
        leg_tasks.append(get_trains_cached(source, mid, date_str))
        leg_tasks.append(get_trains_cached(mid, destination, date_str))

    leg_results = await asyncio.gather(*leg_tasks, return_exceptions=True)
    all_trains = list(direct_trains)
    for res in leg_results:
        if isinstance(res, list):
            all_trains.extend(res)

    # Deduplicate
    unique_trains_map = {f"{t.train_number}_{t.source_station}_{t.destination_station}": t for t in all_trains}
    unique_trains = list(unique_trains_map.values())
    train_class_map = {t.train_number: t.class_list for t in unique_trains if t.class_list}
    logger.info(f"Step 3: Built graph with {len(unique_trains)} unique train segments")

    # Build graph and find routes (allowing multi-leg now)
    graph = RouteGraph()
    graph.build_graph(unique_trains)
    routes = graph.find_routes(source, destination, constraints, date_str)
    logger.info(f"Step 4: Discovered {len(routes)} candidate routes")

    # Fetch availability for all unique legs across all routes
    unique_legs_map = {}
    for route in routes:
        for leg in route.legs:
            key = (leg.train_number, leg.from_station, leg.to_station, leg.date)
            if key not in unique_legs_map:
                unique_legs_map[key] = leg

    unique_keys = list(unique_legs_map.keys())
    parallel_results = await asyncio.gather(
        *[fetch_leg_availability(unique_legs_map[k], train_class_map, quota) for k in unique_keys],
        return_exceptions=True
    )
    avail_lookup = {
        k: (r if isinstance(r, list) else [])
        for k, r in zip(unique_keys, parallel_results)
    }

    assembled = assemble_routes(routes, avail_lookup)

    # Step 5: Boarding-point simplification for multi-leg routes
    logger.info("Step 5: Checking for boarding-point simplification...")
    simplified_routes = []
    for route in assembled:
        if route.connections > 0 and route.is_fully_confirmed:
            simp = await try_simplify_route(route, source)
            if simp:
                simplified_routes.append(simp)
    logger.info(f"Found {len(simplified_routes)} simplified routes")

    # Combine: direct (even if no seats) + multi-leg + simplified
    all_routes = direct_assembled + assembled + simplified_routes

    # Deduplicate by leg signature
    seen = set()
    deduped = []
    for r in all_routes:
        sig = tuple((l.train_number, l.from_station, l.to_station) for l in r.legs)
        if sig not in seen:
            seen.add(sig)
            deduped.append(r)

    # Filter out departed trains and apply only_confirmed
    final_routes = []
    for r in deduped:
        has_departed = any(any("DEPARTED" in _get_status(av) for av in leg.availability) for leg in r.legs)
        if has_departed:
            continue
        if only_confirmed and not r.is_fully_confirmed:
            continue
        final_routes.append(r)

    # Sort: confirmed first, then by connections, then by duration
    final_routes.sort(key=lambda x: (not x.is_fully_confirmed, x.connections, x.total_duration_minutes))
    final_routes = final_routes[:20]

    cache.set(full_cache_key, [r.dict() for r in final_routes], ttl_seconds=86400)
    duration_ms = (time.perf_counter() - search_start_time) * 1000
    logger.info(f"Search completed in {duration_ms:.0f}ms. Found {len(final_routes)} routes (incl. multi-leg).")
    return final_routes


@router.get("/{train_number}/schedule")
async def get_train_schedule(train_number: str, date: Optional[str] = None, source: Optional[str] = "NDLS"):
    return await get_schedule_cached(train_number, date or datetime.datetime.now().strftime("%Y-%m-%d"), source=source)
