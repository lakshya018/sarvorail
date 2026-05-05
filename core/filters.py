"""
Constraint-based filtering logic.
"""
from typing import List
from config.settings import MAJOR_JUNCTIONS
from core.geo import get_geo_indexer

def get_candidate_stations(source: str, destination: str, limit: int = 40, offset: int = 0) -> List[str]:
    """
    Find junction stations that are geographically 'on the way'.
    Returns stations ordered by importance: major junctions first, then others.
    Use offset+limit to paginate through candidates (for incremental expansion).
    """
    geo = get_geo_indexer()

    plausible_codes = geo.get_stations_between(source, destination, buffer_km=150.0)

    junctions = []
    for code in plausible_codes:
        if code == source or code == destination:
            continue
        station = geo.get_station(code)
        name = station.get("name", "").upper()
        if " JN" in name or "JUNCTION" in name:
            junctions.append(code)

    nearby_source = geo.get_nearby_stations(source, radius_km=50.0)
    nearby_dest = geo.get_nearby_stations(destination, radius_km=50.0)

    all_candidates = list(set(junctions + nearby_source + nearby_dest))
    major_set = set(MAJOR_JUNCTIONS)
    major_first = [c for c in all_candidates if c in major_set]
    rest = [c for c in all_candidates if c not in major_set]
    ordered = major_first + rest

    if source in ordered: ordered.remove(source)
    if destination in ordered: ordered.remove(destination)

    return ordered[offset:offset + limit]


def get_total_candidate_count(source: str, destination: str) -> int:
    """Get total number of candidate stations available (for pagination)."""
    return len(get_candidate_stations(source, destination, limit=10000, offset=0))
