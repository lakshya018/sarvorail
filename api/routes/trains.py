"""
API endpoints for finding trains and routes.
"""
import asyncio
import datetime
import logging
import time
import json
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, Request

from api.models import TrainSummary, Route, RouteConstraints, StationStop, RouteLeg, AvailabilityResult
from core import cache
from scraper.ntes_scraper import get_trains_between_stations, get_train_schedule as fetch_train_schedule
from core.graph import RouteGraph
from core.geo import get_geo_indexer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Trains & Routes"])

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

@router.get("/trains", response_model=List[TrainSummary])
async def get_trains(
    source: str = Query(..., description="Source station code", examples=["NDLS"]),
    destination: str = Query(..., description="Destination station code", examples=["LKO"]),
    date: datetime.date = Query(..., description="Date of journey", examples=["2024-11-25"]),
):
    date_str = date.strftime("%Y-%m-%d")
    cache_key = f"trains_direct:{source}:{destination}:{date_str}"

    cached = cache.get(cache_key)
    if cached:
        return [TrainSummary(**t) for t in cached]

    trains = await get_trains_between_stations(source, destination, date_str)
    summaries = [TrainSummary(**t.dict()) for t in trains]

    if summaries:
        cache.set(cache_key, [s.dict() for s in summaries], cache.TRAINS_BETWEEN_TTL)

    return summaries

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
    try:
        return await asyncio.wait_for(_get_routes_impl(request, source, destination, date, max_duration_hours, max_connections, min_layover_mins, max_layover_mins, classes, departure_after, departure_before, arrival_before, only_confirmed, quota), timeout=60.0)
    except asyncio.TimeoutError:
        logger.warning(f"Route search timeout for {source}->{destination}")
        return []

async def _get_routes_impl(request, source, destination, date, max_duration_hours, max_connections, min_layover_mins, max_layover_mins, classes, departure_after, departure_before, arrival_before, only_confirmed, quota):
    """Implementation of route search."""
    search_start_time = time.perf_counter()
    date_str = date.strftime("%Y-%m-%d")

    # Validate inputs
    if not source or not destination:
        return []

    # --- TARGET ARCHITECTURE: SINGLE CACHE KEY ---
    full_cache_key = f"routes_full:{source}:{destination}:{date_str}:{quota}"
    cached_routes = cache.get(full_cache_key)
    if cached_routes:
        logger.info(f"✨ [Cache Hit] Full routes for {source}->{destination}")
        return [Route(**r) if isinstance(r, dict) else r for r in cached_routes]

    # --- TARGET ARCHITECTURE: SINGLE API CALL ---
    # We only fetch direct trains for the primary source/destination pair
    trains = await get_trains_between_stations(source, destination, date_str)
    unique_trains = [TrainSummary(**t.dict()) for t in trains]

    # Build a map from train_number -> class_list for use in availability checking.
    train_class_map: dict = {t.train_number: t.class_list for t in unique_trains if t.class_list}

    # Step 2: Build graph and find valid routes (Direct only now)
    graph = RouteGraph()
    graph.build_graph(unique_trains)
    
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
    
    routes = graph.find_routes(source, destination, constraints, date_str)
    
    # 1. Identify all unique legs
    unique_legs_map = {}
    for route in routes:
        for leg in route.legs:
            key = (leg.train_number, leg.from_station, leg.to_station, leg.date)
            if key not in unique_legs_map:
                unique_legs_map[key] = leg

    irctc_scraper = request.app.state.irctc_scraper

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
        except: pass
        return None

    async def _fetch_availability(leg, quota_code: str):
        classes_to_check = train_class_map.get(leg.train_number) or ["SL", "3A", "2A", "1A"]
        tasks = [fetch_one(leg.train_number, leg.from_station, leg.to_station, leg.date, c, quota_code) for c in classes_to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [AvailabilityResult(**r) if isinstance(r, dict) else r for r in results if r]

    # Fetch unique availabilities sequentially or in very small batches to avoid pool exhaustion
    avail_lookup = {}
    unique_keys = list(unique_legs_map.keys())
    for key in unique_keys:
        leg = unique_legs_map[key]
        result = await _fetch_availability(leg, quota)
        avail_lookup[key] = result if result else []

    # Assemble and filter
    final_routes = []
    for route in routes:
        for leg in route.legs:
            key = (leg.train_number, leg.from_station, leg.to_station, leg.date)
            leg.availability = avail_lookup.get(key, [])
        
        # IN-MEMORY FILTERING
        has_seats = any(any(a.status in ["AVAILABLE", "CURR_AVBL"] or "AVBL" in a.status for a in leg.availability) for leg in route.legs)
        if not only_confirmed or has_seats:
            final_routes.append(route)

    # --- TARGET ARCHITECTURE: CACHE FINAL RESULT ONCE ---
    final_routes_data = [r.dict() for r in final_routes[:20]]
    cache.set(full_cache_key, final_routes_data, ttl_seconds=86400)

    duration_ms = (time.perf_counter() - search_start_time) * 1000
    logger.info(f"Search completed in {duration_ms:.2f}ms. Found {len(final_routes)} routes.")
    return final_routes[:20]

@router.get("/{train_number}/schedule")
async def get_train_schedule(train_number: str, date: Optional[str] = None, source: Optional[str] = "NDLS"):
    return await get_schedule_cached(train_number, date or datetime.datetime.now().strftime("%Y-%m-%d"), source=source)
