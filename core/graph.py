"""
Graph-based route finder for trains using BFS.
"""
import logging
from typing import List, Dict
from datetime import datetime, timedelta

from api.models import Train, Route, RouteLeg, RouteConstraints

logger = logging.getLogger(__name__)

class RouteGraph:
    def __init__(self):
        # adjacency list: station_code -> List[Train]
        self.graph: Dict[str, List[Train]] = {}

    def build_graph(self, trains: List[Train]) -> None:
        """Builds adjacency graph where nodes are station codes and edges are trains."""
        for train in trains:
            if train.source_station not in self.graph:
                self.graph[train.source_station] = []
            self.graph[train.source_station].append(train)

    def find_routes(self, source: str, destination: str, constraints: RouteConstraints, start_date_str: str) -> List[Route]:
        """
        Find optimal routes using A* algorithm with geographic heuristic.
        """
        import heapq
        from datetime import datetime, timedelta
        from core.geo import get_geo_indexer
        
        geo = get_geo_indexer()
        dest_stn = geo.get_station(destination)
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        
        def get_heuristic(station_code):
            if not dest_stn: return 0
            stn = geo.get_station(station_code)
            if not stn: return 0
            # Haversine distance in km / average train speed (60km/h) * 60 to get minutes
            dist = geo.haversine_distance(stn["lat"], stn["lon"], dest_stn["lat"], dest_stn["lon"])
            return (dist / 60.0) * 60.0 

        # Queue stores: (f_score, total_duration, tie_breaker, current_station, path_legs, current_time, visited)
        # f_score = g_score (actual duration) + h_score (heuristic)
        count = 0
        queue = [(0, 0, count, source, [], start_date, {source})]
        routes = []
        
        logger.debug(f"A* pathfinding: {source} -> {destination}")

        while queue:
            f, duration, _, current_station, path_legs, current_time, visited = heapq.heappop(queue)
            
            if current_station == destination:
                routes.append(Route(
                    legs=path_legs,
                    total_duration_minutes=int(duration),
                    total_distance_km=0,
                    connections=len(path_legs) - 1,
                    is_fully_confirmed=False
                ))
                if len(routes) >= 50: break # Cap for performance
                continue

            if len(path_legs) >= constraints.max_connections + 1:
                continue

            for train in self.graph.get(current_station, []):
                if train.destination_station in visited:
                    continue
                
                # Check if train runs on the current_time day.
                # Guard: if days_of_run is empty (IRCTC didn't return running-day flags),
                # treat the train as running every day rather than silently dropping it.
                day_name = current_time.strftime('%a').upper()
                if train.days_of_run and day_name not in train.days_of_run:
                    if not path_legs: continue # First leg must be on start_date
                
                try:
                    dep_h, dep_m = map(int, train.departure_time.split(':'))
                    arr_h, arr_m = map(int, train.arrival_time.split(':'))
                    
                    # Departure on the same day as current_time
                    dep_dt = current_time.replace(hour=dep_h, minute=dep_m, second=0, microsecond=0)
                    
                    # If it's a connection, ensure layover
                    if path_legs:
                        layover = (dep_dt - current_time).total_seconds() / 60
                        if layover < constraints.min_layover_minutes:
                            # Try next day
                            dep_dt += timedelta(days=1)
                            layover = (dep_dt - current_time).total_seconds() / 60
                        
                        if layover > constraints.max_layover_minutes:
                            continue
                    else:
                        # First leg: if departure is earlier than "now" (if searching for today)
                        # But for future dates, we just use the date.
                        pass

                    # Calculate arrival
                    arr_dt = dep_dt.replace(hour=arr_h, minute=arr_m)
                    if arr_dt <= dep_dt:
                        arr_dt += timedelta(days=1)
                    
                    leg_duration = (arr_dt - dep_dt).total_seconds() / 60
                    total_duration = duration + leg_duration
                    if path_legs:
                        total_duration += (dep_dt - current_time).total_seconds() / 60

                    if total_duration > constraints.max_total_duration_hours * 60:
                        continue

                    new_leg = RouteLeg(
                        train_number=train.train_number,
                        train_name=train.train_name,
                        from_station=current_station,
                        to_station=train.destination_station,
                        date=dep_dt.strftime("%Y-%m-%d"),
                        departure_time=dep_dt.isoformat(),
                        arrival_time=arr_dt.isoformat(),
                        duration_minutes=int(leg_duration)
                    )
                    
                    h_score = get_heuristic(train.destination_station)
                    g_score = total_duration
                    f_score = g_score + h_score
                    
                    count += 1
                    new_visited = visited | {train.destination_station}
                    heapq.heappush(queue, (f_score, total_duration, count, train.destination_station, path_legs + [new_leg], arr_dt, new_visited))
                    
                except Exception as e:
                    logger.error(f"Error processing train {train.train_number}: {e}")
                    continue

        return routes
