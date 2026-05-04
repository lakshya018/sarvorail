"""
IRCTC Scraper — uses IRCTC's internal avlFarenquiry API directly.
No browser automation needed. Fast, reliable JSON responses.
"""
import logging
import asyncio
import uuid
import time
import httpx
import re
from typing import List, Optional
from datetime import datetime

from api.models import AvailabilityResult
from config.settings import MAX_RETRIES

logger = logging.getLogger(__name__)

# IRCTC internal availability API
_BASE_URL = "https://www.irctc.co.in/eticketing/protected/mapps1/avlFarenquiry"

def _make_headers(referer: str = "https://www.irctc.co.in/nget/booking/train-list") -> dict:
    """Generate per-request headers including the dynamic greq fingerprint."""
    greq = f"{int(time.time() * 1000)}:{uuid.uuid4()}"
    return {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.0",
        "Content-Type": "application/json; charset=UTF-8",
        "Content-Language": "en",
        "Origin": "https://www.irctc.co.in",
        "Referer": referer,
        "bmirak": "webbm",
        "greq": greq,
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }

# Shared client with cookie support
_client = httpx.AsyncClient(
    headers=_make_headers(), 
    timeout=httpx.Timeout(40.0, connect=10.0), 
    follow_redirects=True,
    cookies={"bmirak": "webbm"} # Pre-seed some known values
)

_ALL_CLASSES = ["SL", "3A", "3E", "2A", "1A", "CC", "EC", "2S"]


def _parse_status(availability_status: str, availability_type: str) -> tuple[str, Optional[int], Optional[int]]:
    """Parse IRCTC availablityStatus string into (status, available_count, waitlist_number)."""
    s = str(availability_status).upper().strip()
    a_type = str(availability_type)
    
    available_count: Optional[int] = None
    waitlist_number: Optional[int] = None
    status = "NOT_AVAILABLE"
    
    # 1. Determine Status Category (Check negative statuses FIRST)
    if "DEPARTED" in s:
        status = "TRAIN_DEPARTED"
    elif any(x in s for x in ["REGRET", "NOT AVAILABLE", "NOT_AVAILABLE", "CANCELLED", "DOES NOT RUN"]):
        status = "NOT_AVAILABLE"
    elif a_type == "1" or any(x in s for x in ["AVAILABLE", "CURR_AVBL", "AVBL"]):
        status = "AVAILABLE"
    elif a_type == "3" or any(x in s for x in ["WL", "WAITLIST", "RLWL", "PQWL", "GNWL"]):
        status = "WAITLIST"
    elif a_type == "2" or "RAC" in s:
        status = "RAC"
    
    # Check if a_type is 0 (often means not available or error)
    if a_type == "0" and status == "NOT_AVAILABLE":
        status = "NOT_AVAILABLE"
        
    # 2. Extract Numbers
    # Format 'RLWL45/WL23' -> numbers are [45, 23]. 23 is the current status.
    # Format 'AVAILABLE-0005' -> number is [5].
    nums = re.findall(r"\d+", s)
    
    if status == "AVAILABLE":
        if nums:
            available_count = int(nums[-1])
        else:
            # If type 1 but no number, it's just 'AVAILABLE'
            available_count = None 
    elif status in ["WAITLIST", "RAC"]:
        if nums:
            # For 'RLWL45/WL23', the current WL is the last number
            waitlist_number = int(nums[-1])
    logger.debug(f"Parsed IRCTC status: '{s}' (Type {a_type}) -> {status}")
    return status, available_count, waitlist_number


class IRCTCScraper:
    _session_lock = asyncio.Lock()
    _initialized = False

    def __init__(self):
        pass

    async def _ensure_session(self):
        """Ensure IRCTC session is active. Uses a lock to prevent concurrent refresh storms."""
        async with self._session_lock:
            if not _client.cookies or not self._initialized:
                logger.info("Initializing fresh IRCTC session...")
                try:
                    await _client.get("https://www.irctc.co.in/nget/train-search", 
                                    headers=_make_headers("https://www.google.com"),
                                    timeout=20.0)
                    self._initialized = True
                except Exception as e:
                    logger.error(f"Session initialization failed: {e}")

    async def get_seat_availability(
        self,
        train_number: str,
        source: str,
        destination: str,
        date: str,
        class_code: str,
        quota: str = "GN",
    ) -> AvailabilityResult:
        """Fetch availability for a specific class with concurrency protection."""
        await self._ensure_session()
        
        # Convert date
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            date_obj = datetime.strptime(date, "%Y%m%d")
        
        irctc_date = date_obj.strftime("%Y%m%d")
        url = f"{_BASE_URL}/{train_number}/{irctc_date}/{source}/{destination}/{class_code}/{quota}/N"
        
        payload = {
            "paymentFlag": "N", "concessionBooking": False, "ftBooking": False,
            "loyaltyRedemptionBooking": False, "ticketType": "E", "quotaCode": quota,
            "moreThanOneDay": True, "returnJourney": False, "trainNumber": train_number,
            "fromStnCode": source, "toStnCode": destination, "isLogedinReq": False,
            "journeyDate": irctc_date, "classCode": class_code,
        }

        for attempt in range(MAX_RETRIES):
            try:
                resp = await _client.post(url, json=payload, headers=_make_headers())
                
                if resp.status_code == 403:
                    logger.warning(f"IRCTC 403. Refreshing session (Attempt {attempt+1})...")
                    # Force re-init on 403
                    self._initialized = False
                    await self._ensure_session()
                    continue

                resp.raise_for_status()
                data = resp.json()

                # Find the entry for the exact requested date
                avl_list = data.get("avlDayList", [])
                target_entry = None
                req_d, req_m, req_y = date_obj.day, date_obj.month, date_obj.year

                for entry in avl_list:
                    edate = str(entry.get("availablityDate", ""))
                    if not edate: continue
                    try:
                        # Split "4-5-2026" or "04-05-2026"
                        parts = edate.split("-")
                        if len(parts) == 3:
                            if int(parts[0]) == req_d and int(parts[1]) == req_m and int(parts[2]) == req_y:
                                target_entry = entry
                                break
                    except: continue

                if not target_entry:
                    logger.warning(f"❌ [Scraper] No exact match for {req_d}-{req_m}-{req_y} in IRCTC response for {train_number}")
                    return AvailabilityResult(
                        class_code=class_code,
                        status="NOT_AVAILABLE",
                        available_count=None,
                        waitlist_number=None,
                        fare=None
                    )
                
                logger.debug(f"[Scraper] Date match for {train_number}: {target_entry.get('availablityStatus')}")

                if target_entry:
                    status, available_count, waitlist_number = _parse_status(
                        target_entry.get("availablityStatus", ""),
                        target_entry.get("availablityType", "0"),
                    )
                else:
                    status, available_count, waitlist_number = "NOT_AVAILABLE", None, None

                fare = None
                try:
                    fare = float(data.get("totalFare", 0)) or None
                except (ValueError, TypeError):
                    pass

                return AvailabilityResult(
                    class_code=class_code,
                    status=status,
                    available_count=available_count,
                    waitlist_number=waitlist_number,
                    fare=fare,
                )

            except httpx.HTTPStatusError as e:
                logger.warning(f"IRCTC API HTTP error on attempt {attempt + 1}: {e.response.status_code}")
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.warning(f"IRCTC API error on attempt {attempt + 1}: {e}")
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise Exception(f"Failed to get availability for {train_number}/{class_code} after {MAX_RETRIES} retries")

    async def get_all_classes_availability(
        self,
        train_number: str,
        source: str,
        destination: str,
        date: str,
        quota: str = "GN",
    ) -> List[AvailabilityResult]:
        """
        Fetch availability for all standard classes.
        Sequential with small delay to avoid 403 Forbidden from Akamai.
        """
        valid: List[AvailabilityResult] = []
        for cls in _ALL_CLASSES:
            try:
                res = await self.get_seat_availability(train_number, source, destination, date, cls, quota)
                valid.append(res)
                await asyncio.sleep(0.5) # Anti-ban delay
            except Exception as e:
                logger.warning(f"Skipping class {cls} — error: {e}")
        return valid
