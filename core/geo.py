import json
import logging
import math
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class GeoIndexer:
    def __init__(self, stations_file: str = "stations.json"):
        self.stations: Dict[str, dict] = {}
        self._load_data(stations_file)

    def _load_data(self, file_path: str):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                for feature in data.get("features", []):
                    props = feature.get("properties", {})
                    geom = feature.get("geometry")
                    if props.get("code") and geom and geom.get("coordinates"):
                        # GeoJSON is [lon, lat]
                        lon, lat = geom["coordinates"]
                        self.stations[props["code"]] = {
                            "name": props.get("name"),
                            "lat": lat,
                            "lon": lon,
                            "state": props.get("state")
                        }
            logger.info(f"Loaded {len(self.stations)} stations from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load stations.json: {e}")

    def get_station(self, code: str) -> Optional[dict]:
        return self.stations.get(code.upper())

    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in km."""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * \
            math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_nearby_stations(self, code: str, radius_km: float = 15.0) -> List[str]:
        """Find stations within a radius of a given station code."""
        target = self.get_station(code)
        if not target:
            return []

        nearby = []
        for other_code, data in self.stations.items():
            if other_code == code:
                continue
            dist = self.haversine_distance(target["lat"], target["lon"], data["lat"], data["lon"])
            if dist <= radius_km:
                nearby.append(other_code)
        
        return nearby

    def search_stations(self, query: str, limit: int = 10) -> List[dict]:
        """Search stations by code or name."""
        if not query:
            return []
        
        query = query.upper()
        results = []
        for code, data in self.stations.items():
            if query in code or (data["name"] and query in data["name"].upper()):
                results.append({
                    "code": code,
                    "name": data["name"],
                    "state": data["state"]
                })
            if len(results) >= limit:
                break
        return results

    def get_stations_between(self, source_code: str, dest_code: str, buffer_km: float = 50.0) -> List[str]:
        """
        Find stations that are geographically 'on the way' between source and destination.
        Useful for narrowing down intermediate junction candidates.
        """
        src = self.get_station(source_code)
        dst = self.get_station(dest_code)
        if not src or not dst:
            return []

        # Calculate bounding box with buffer
        min_lat = min(src["lat"], dst["lat"]) - (buffer_km / 111.0)
        max_lat = max(src["lat"], dst["lat"]) + (buffer_km / 111.0)
        min_lon = min(src["lon"], dst["lon"]) - (buffer_km / 111.0)
        max_lon = max(src["lon"], dst["lon"]) + (buffer_km / 111.0)

        candidates = []
        for code, data in self.stations.items():
            if min_lat <= data["lat"] <= max_lat and min_lon <= data["lon"] <= max_lon:
                candidates.append(code)
        
        return candidates

# Singleton instance
_indexer = None

def get_geo_indexer():
    global _indexer
    if _indexer is None:
        _indexer = GeoIndexer()
    return _indexer
