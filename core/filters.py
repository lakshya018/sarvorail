"""
Constraint-based filtering logic.
"""
from typing import List
from config.settings import MAJOR_JUNCTIONS
from core.geo import get_geo_indexer

def get_candidate_stations(source: str, destination: str) -> List[str]:
    """
    Find ALL junction stations that are geographically 'on the way'.
    This scans the entire stations.json for stations with 'JN' in their name.
    """
    geo = get_geo_indexer()
    
    # 1. Get stations that are geographically between source and destination (with 150km buffer)
    plausible_codes = geo.get_stations_between(source, destination, buffer_km=150.0)
    
    # 2. Filter for junctions
    junctions = []
    for code in plausible_codes:
        if code == source or code == destination:
            continue
            
        station = geo.get_station(code)
        name = station.get("name", "").upper()
        
        # Check if it's a junction (contains JN or JUNCTION)
        if " JN" in name or "JUNCTION" in name:
            junctions.append(code)

    # 3. Add ALL stations near source and destination (to catch local hops like Pune -> Khadki)
    nearby_source = geo.get_nearby_stations(source, radius_km=50.0)
    nearby_dest = geo.get_nearby_stations(destination, radius_km=50.0)
    
    # Combine and deduplicate, putting MAJOR_JUNCTIONS first so the cap keeps the
    # most important ones and only discards obscure local stations.
    all_candidates = list(set(junctions + nearby_source + nearby_dest))
    major_first = [c for c in all_candidates if c in set(MAJOR_JUNCTIONS)]
    rest = [c for c in all_candidates if c not in set(MAJOR_JUNCTIONS)]
    ordered = major_first + rest

    if source in ordered: ordered.remove(source)
    if destination in ordered: ordered.remove(destination)

    return ordered[:40]
