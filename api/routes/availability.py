"""
API endpoints for seat availability.
"""
import datetime
from typing import List, Optional
from fastapi import APIRouter, Query, Request

from api.models import AvailabilityResult

router = APIRouter(prefix="/api/v1", tags=["Availability"])

@router.get("/availability", response_model=List[AvailabilityResult])
async def get_availability(
    request: Request,
    train_number: str = Query(..., description="5-digit train number", example="12004"),
    source: str = Query(..., description="Source station code (e.g., NDLS for New Delhi)", example="NDLS"),
    destination: str = Query(..., description="Destination station code (e.g., LKO for Lucknow)", example="LKO"),
    date: datetime.date = Query(..., description="Date of journey", example="2024-11-25"),
    class_code: Optional[str] = Query(None, description="Class code (e.g., 3A, SL, 1A)", example="3A")
):
    irctc_scraper = request.app.state.irctc_scraper
    date_str = date.strftime("%Y-%m-%d")
    
    if class_code:
        result = await irctc_scraper.get_seat_availability(train_number, source, destination, date_str, class_code)
        return [result]
    else:
        results = await irctc_scraper.get_all_classes_availability(train_number, source, destination, date_str)
        return results
