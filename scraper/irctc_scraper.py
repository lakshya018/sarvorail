"""
IRCTC Scraper — uses IRCTC's internal avlFarenquiry API directly.
Uses curl_cffi to impersonate Chrome's TLS fingerprint, bypassing Akamai bot detection.
"""
import logging
import asyncio
import uuid
import time
import re
import os
from typing import List, Optional
from datetime import datetime
from curl_cffi import requests as cffi_requests
from curl_cffi import CurlHttpVersion

from api.models import AvailabilityResult
from config.settings import MAX_RETRIES

logger = logging.getLogger(__name__)

# IRCTC internal availability API
_BASE_URL = "https://www.irctc.co.in/eticketing/protected/mapps1/avlFarenquiry"

# Browser impersonation profile - matches Chrome TLS fingerprint
_IMPERSONATE = "chrome120"

# Optional proxy for cloud environments where IRCTC blocks the host IP
_PROXY = os.getenv("PROXY_URL")


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


# Shared async session with browser TLS fingerprint
# Force HTTP/1.1 to avoid HTTP/2 stream errors on serverless platforms (Vercel)
_session_kwargs = dict(
    impersonate=_IMPERSONATE,
    timeout=30,
    http_version=CurlHttpVersion.V1_1,
)
if _PROXY:
    _session_kwargs["proxy"] = _PROXY
    logger.info(f"Using proxy for IRCTC: {_PROXY[:30]}...")

_client = cffi_requests.AsyncSession(**_session_kwargs)

_ALL_CLASSES = ["SL", "3A", "3E", "2A", "1A", "CC", "EC", "2S"]


def _parse_status(availability_status: str, availability_type: str) -> tuple[str, Optional[int], Optional[int]]:
    """Parse IRCTC availablityStatus string into (status, available_count, waitlist_number)."""
    s = str(availability_status).upper().strip()
    a_type = str(availability_type)

    available_count: Optional[int] = None
    waitlist_number: Optional[int] = None
    status = "NOT_AVAILABLE"

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

    if a_type == "0" and status == "NOT_AVAILABLE":
        status = "NOT_AVAILABLE"

    nums = re.findall(r"\d+", s)

    if status == "AVAILABLE":
        if nums:
            available_count = int(nums[-1])
    elif status in ["WAITLIST", "RAC"]:
        if nums:
            waitlist_number = int(nums[-1])
    logger.debug(f"Parsed IRCTC status: '{s}' (Type {a_type}) -> {status}")
    return status, available_count, waitlist_number


class IRCTCScraper:
    _session_lock = asyncio.Lock()
    _initialized = False

    def __init__(self):
        pass

    async def _ensure_session(self):
        """No-op. curl_cffi handles TLS fingerprinting; bmirak header is sufficient."""
        self._initialized = True

    async def get_seat_availability(
        self,
        train_number: str,
        source: str,
        destination: str,
        date: str,
        class_code: str,
        quota: str = "GN",
    ) -> AvailabilityResult:
        """Fetch availability for a specific class."""
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

        max_retries = 2
        for attempt in range(max_retries):
            try:
                resp = await _client.post(
                    url,
                    json=payload,
                    headers=_make_headers(),
                    timeout=20,
                )

                if resp.status_code == 403:
                    logger.warning(f"IRCTC 403 (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                    continue

                if resp.status_code != 200:
                    logger.warning(f"IRCTC HTTP {resp.status_code}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue

                data = resp.json()

                avl_list = data.get("avlDayList", [])
                target_entry = None
                req_d, req_m, req_y = date_obj.day, date_obj.month, date_obj.year

                for entry in avl_list:
                    edate = str(entry.get("availablityDate", ""))
                    if not edate: continue
                    try:
                        parts = edate.split("-")
                        if len(parts) == 3:
                            if int(parts[0]) == req_d and int(parts[1]) == req_m and int(parts[2]) == req_y:
                                target_entry = entry
                                break
                    except: continue

                if not target_entry:
                    return AvailabilityResult(
                        class_code=class_code, status="NOT_AVAILABLE",
                        available_count=None, waitlist_number=None, fare=None
                    )

                status, available_count, waitlist_number = _parse_status(
                    target_entry.get("availablityStatus", ""),
                    target_entry.get("availablityType", "0"),
                )

                fare = None
                try:
                    fare = float(data.get("totalFare", 0)) or None
                except (ValueError, TypeError):
                    pass

                return AvailabilityResult(
                    class_code=class_code, status=status,
                    available_count=available_count, waitlist_number=waitlist_number, fare=fare,
                )

            except Exception as e:
                logger.warning(f"IRCTC API error on attempt {attempt + 1}: {type(e).__name__}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        logger.warning(f"IRCTC unavailable for {train_number}/{class_code}. Returning NOT_AVAILABLE.")
        return AvailabilityResult(
            class_code=class_code, status="NOT_AVAILABLE",
            available_count=None, waitlist_number=None, fare=None,
        )

    async def get_all_classes_availability(
        self,
        train_number: str,
        source: str,
        destination: str,
        date: str,
        quota: str = "GN",
    ) -> List[AvailabilityResult]:
        """Fetch availability for all standard classes in parallel."""
        tasks = [
            self.get_seat_availability(train_number, source, destination, date, cls, quota)
            for cls in _ALL_CLASSES
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, AvailabilityResult)]
