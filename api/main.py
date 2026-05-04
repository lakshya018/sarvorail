"""
FastAPI application and startup sequence.
"""
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from scraper.irctc_scraper import IRCTCScraper
from config.settings import LOG_LEVEL

from api.routes import trains, availability
from api.models import HealthStatus, Station
from core.geo import get_geo_indexer

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

irctc_scraper = IRCTCScraper()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Store instances in app state
    app.state.irctc_scraper = irctc_scraper
    logger.info("App started — using in-memory cache (cachetools)")

    yield

    logger.info("App shutdown")

app = FastAPI(title="SarvoRail API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "details": str(exc)}
    )

app.include_router(trains.router)
app.include_router(availability.router)

@app.get("/api/v1/stations/search", response_model=list[Station])
async def search_stations(query: str):
    geo = get_geo_indexer()
    results = geo.search_stations(query)
    
    matches = []
    for r in results:
        full_data = geo.get_station(r["code"])
        matches.append(Station(
            station_code=r["code"],
            station_name=r["name"],
            state=r["state"] or "Unknown",
            latitude=full_data.get("lat"),
            longitude=full_data.get("lon"),
            is_major_junction=False # Placeholder
        ))
    return matches

@app.get("/api/v1/health", response_model=HealthStatus)
async def health_check():
    return HealthStatus(
        status="ok",
        redis_connected=False,  # Using in-memory cache now
        active_sessions=0,
        total_sessions=0,
        uptime_seconds=0.0
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
