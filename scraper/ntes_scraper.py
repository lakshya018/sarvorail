"""
IRCTC Scraper for finding trains between stations and schedules.
Uses IRCTC's internal JSON APIs discovered by the user.
"""
import logging
import asyncio
import httpx
from typing import List, Optional
from datetime import datetime

from api.models import Train, StationStop
from config.settings import MAX_RETRIES
from scraper.irctc_scraper import _make_headers, _client

logger = logging.getLogger(__name__)

_TRAINS_BETWEEN_URL = "https://www.irctc.co.in/eticketing/protected/mapps1/altAvlEnq/TC"

async def get_trains_between_stations(source: str, destination: str, date: str) -> List[Train]:
    """Fetch all trains between two stations on a specific date using IRCTC API."""
    try:
        return await asyncio.wait_for(_get_trains_impl(source, destination, date), timeout=45.0)
    except asyncio.TimeoutError:
        logger.warning(f"Train search timeout for {source}->{destination}")
        return []

async def _get_trains_impl(source: str, destination: str, date: str) -> List[Train]:
    """Implementation of train search with retry logic."""
    # Convert YYYY-MM-DD → YYYYMMDD
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        irctc_date = date_obj.strftime("%Y%m%d")
    except ValueError:
        irctc_date = date.replace("-", "")

    payload = {
        "concessionBooking": False, "srcStn": source, "destStn": destination,
        "jrnyClass": "", "jrnyDate": irctc_date, "quotaCode": "GN",
        "currentBooking": "false", "flexiFlag": False, "handicapFlag": False,
        "ticketType": "E", "loyaltyRedemptionBooking": False, "ftBooking": False
    }

    # We use a dummy instance just to leverage the class-level session lock
    from scraper.irctc_scraper import IRCTCScraper
    scraper = IRCTCScraper()

    for attempt in range(MAX_RETRIES):
        try:
            await scraper._ensure_session()
            headers = _make_headers(referer="https://www.irctc.co.in/nget/train-search")
            resp = await asyncio.wait_for(
                _client.post(_TRAINS_BETWEEN_URL, json=payload, headers=headers),
                timeout=10.0
            )
            
            if resp.status_code == 403:
                logger.warning(f"IRCTC 403 on search. Refreshing...")
                scraper._initialized = False
                await scraper._ensure_session()
                continue

            resp.raise_for_status()
            data = resp.json()
            
            if not isinstance(data, dict):
                logger.warning(f"IRCTC trains search expected dict, got {type(data)}")
                return []

            if data.get("errorMessage"):
                logger.info(f"IRCTC search {source}->{destination}: {data.get('errorMessage')}")
                return []

            train_list = data.get("trainBtwnStnsList", [])
            if not isinstance(train_list, list):
                return []

            logger.debug(f"IRCTC found {len(train_list)} trains between {source} and {destination}")
            results = []
            for t in train_list:
                if not isinstance(t, dict): continue
                days = []
                day_map = {
                    "runningMon": "MON", "runningTue": "TUE", "runningWed": "WED",
                    "runningThu": "THU", "runningFri": "FRI", "runningSat": "SAT", "runningSun": "SUN"
                }
                for key, day_name in day_map.items():
                    if t.get(key) == "Y": days.append(day_name)

                # Check if train is explicitly marked as NOT RUNNING on this specific date
                if t.get('trainRunningOnDate') == 'N':
                    logger.warning(f"Train {t.get('trainNumber')} is NOT RUNNING on this date. Skipping.")
                    continue

                duration_str = t.get("duration", "00:00")
                try:
                    h, m = map(int, duration_str.split(":"))
                    duration_mins = h * 60 + m
                except:
                    duration_mins = 0

                # Parse which classes this train actually offers
                # Use `or []` — key may be present with a null value, which .get(default) won't catch
                raw_classes = t.get("avlClasses") or []
                class_list = []
                for c in raw_classes:
                    if isinstance(c, dict):
                        code = c.get("classCode")
                        if code: class_list.append(code)
                    elif isinstance(c, str):
                        class_list.append(c)

                results.append(Train(
                    train_number=t.get("trainNumber"),
                    train_name=t.get("trainName"),
                    departure_time=t.get("departureTime"),
                    arrival_time=t.get("arrivalTime"),
                    duration_minutes=duration_mins,
                    days_of_run=days,
                    source_station=t.get("fromStnCode"),
                    destination_station=t.get("toStnCode"),
                    class_list=class_list,
                ))
            return results
        except Exception as e:
            logger.warning(f"IRCTC trains search failed (Attempt {attempt + 1}): {e}")
            await asyncio.sleep(2.0)

    return []

async def get_train_schedule(train_number: str, date: Optional[str] = None, source: Optional[str] = "NDLS") -> List[StationStop]:
    """Verified schedule fetcher using dynamic date and starting station."""
    try:
        return await asyncio.wait_for(_get_schedule_impl(train_number, date, source), timeout=40.0)
    except asyncio.TimeoutError:
        logger.warning(f"Schedule fetch timeout for {train_number}")
        return []

async def _get_schedule_impl(train_number: str, date: Optional[str], source: Optional[str]) -> List[StationStop]:
    """Implementation of schedule fetch with retry logic."""
    jrny_date = date.replace("-", "") if date else datetime.now().strftime("%Y%m%d")
    stn_code = source or "NDLS"
    url = f"https://www.irctc.co.in/eticketing/protected/mapps1/trnscheduleenquiry/{train_number}?journeyDate={jrny_date}&startingStationCode={stn_code}"

    from scraper.irctc_scraper import IRCTCScraper
    scraper = IRCTCScraper()

    try:
        await scraper._ensure_session()
        resp = await asyncio.wait_for(
            _client.get(url, headers=_make_headers()),
            timeout=10.0
        )

        if resp.status_code == 403:
            scraper._initialized = False
            await scraper._ensure_session()
            resp = await asyncio.wait_for(
                _client.get(url, headers=_make_headers()),
                timeout=30.0
            )

        if resp.status_code != 200: return []

        data = resp.json()
        station_list = data.get("stationList", [])
        stops = []
        for s in station_list:
            try:
                arr = s.get("arrivalTime")
                dep = s.get("departureTime")
                halt = s.get("haltTime")
                stops.append(StationStop(
                    station_code=str(s.get("stationCode", "")),
                    station_name=str(s.get("stationName", "")),
                    arrival_time=arr if arr != "--" else None,
                    departure_time=dep if dep != "--" else None,
                    halt_minutes=0 if halt == "--" else int(halt.split(":")[0]) if ":" in str(halt) else int(halt or 0),
                    day_number=int(s.get("dayCount", 1) or 1),
                    distance_km=int(s.get("distance", 0) or 0)
                ))
            except: continue
        return stops
    except Exception as e:
        logger.error(f"Schedule fetch failed: {e}")
    return []


