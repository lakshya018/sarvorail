"""
Pydantic models for request and response validation.
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Train(BaseModel):
    train_number: str
    train_name: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    days_of_run: List[str]
    source_station: str
    destination_station: str
    class_list: List[str] = []  # Classes this train actually runs (e.g. SL, 3A, 2A)

class StationStop(BaseModel):
    station_code: str
    station_name: str
    arrival_time: Optional[str]
    departure_time: Optional[str]
    halt_minutes: int = 0
    day_number: int = 1
    distance_km: int = 0

class AvailabilityResult(BaseModel):
    class_code: str
    status: str  # AVAILABLE / RAC / WL / NOT_AVAILABLE
    available_count: Optional[int]
    waitlist_number: Optional[int]
    fare: Optional[float]

class Station(BaseModel):
    station_code: str
    station_name: str
    state: str
    latitude: Optional[float]
    longitude: Optional[float]
    is_major_junction: bool

class RouteLeg(BaseModel):
    train_number: str
    train_name: str
    from_station: str
    to_station: str
    booked_from_station: Optional[str] = None
    actual_boarding_station: Optional[str] = None
    date: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    availability: List[AvailabilityResult] = []

class Route(BaseModel):
    legs: List[RouteLeg]
    total_duration_minutes: int
    total_distance_km: int
    connections: int
    is_fully_confirmed: bool

class RouteConstraints(BaseModel):
    max_total_duration_hours: float
    max_connections: int
    min_layover_minutes: int
    max_layover_minutes: int
    preferred_classes: List[str]
    departure_after: str
    departure_before: str
    arrival_before: str
    only_confirmed: bool

class HealthStatus(BaseModel):
    status: str
    redis_connected: bool
    active_sessions: int
    total_sessions: int
    uptime_seconds: float

class TrainSummary(Train):
    pass
