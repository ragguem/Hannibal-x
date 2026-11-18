"""Monde cinématique sans LOTUSim : reprend `run_fleet` du banc de caractérisation de l'ancienne app.

Chaque navire tourne et accélère vers son point de route avec un taux borné. Sert de faux simulateur au mode
`fake` de l'API et au monde `kinematic` de `sim-bridge`. Positions en mètres dans le repère local (x à l'est,
y au nord), points de route en lat/lon.
"""

import math
from collections.abc import Mapping

METERS_PER_DEGREE_LAT = 111320.0
MAX_TURN_RATE_DEG_PER_S = 4.0
MAX_ACCELERATION_MPS2 = 0.4
MIN_SPEED_MPS = 1.6
SPEED_PER_METER_TO_WAYPOINT = 0.414


class KinematicFleet:
    def __init__(self, origin_lat_lon: tuple[float, float]) -> None:
        self._origin_lat, self._origin_lon = origin_lat_lon
        self._ships: dict[str, dict[str, float]] = {}
        self._last_step_at: float | None = None

    def to_lat_lon(self, east_m: float, north_m: float) -> tuple[float, float]:
        lat = self._origin_lat + north_m / METERS_PER_DEGREE_LAT
        return lat, self._origin_lon + east_m / (METERS_PER_DEGREE_LAT * math.cos(math.radians(lat)))

    def to_local(self, lat: float, lon: float) -> tuple[float, float]:
        east_m = (lon - self._origin_lon) * METERS_PER_DEGREE_LAT * math.cos(math.radians(lat))
        return east_m, (lat - self._origin_lat) * METERS_PER_DEGREE_LAT

    def spawn(self, ships: Mapping[str, tuple[float, float, float]], now: float) -> None:
        self._ships = {
            name: {"x": east_m, "y": north_m, "sog": 0.0, "hdg": heading_deg}
            for name, (east_m, north_m, heading_deg) in ships.items()
        }
        self._last_step_at = now

    def states(self) -> dict[str, dict[str, float]]:
        states = {}
        for name, ship in self._ships.items():
            lat, lon = self.to_lat_lon(ship["x"], ship["y"])
            states[name] = {**ship, "lat": lat, "lon": lon}
        return states

    def steer(self, waypoints: Mapping[str, tuple[float, float]], now: float) -> None:
        elapsed_s = 0.0 if self._last_step_at is None else now - self._last_step_at
        self._last_step_at = now
        max_turn_deg = MAX_TURN_RATE_DEG_PER_S * elapsed_s
        max_speed_change = MAX_ACCELERATION_MPS2 * elapsed_s
        for name, (waypoint_lat, waypoint_lon) in waypoints.items():
            ship = self._ships.get(name)
            if ship is None:
                continue
            waypoint_east, waypoint_north = self.to_local(waypoint_lat, waypoint_lon)
            distance_m = math.hypot(waypoint_east - ship["x"], waypoint_north - ship["y"])
            bearing_deg = (
                math.degrees(math.atan2(waypoint_east - ship["x"], waypoint_north - ship["y"])) % 360
            )
            turn_deg = ((bearing_deg - ship["hdg"] + 540.0) % 360.0) - 180.0
            ship["hdg"] = (ship["hdg"] + max(-max_turn_deg, min(max_turn_deg, turn_deg))) % 360
            target_speed = MIN_SPEED_MPS + SPEED_PER_METER_TO_WAYPOINT * distance_m
            ship["sog"] += max(-max_speed_change, min(max_speed_change, target_speed - ship["sog"]))
        for ship in self._ships.values():
            heading_rad = math.radians(ship["hdg"])
            ship["x"] += ship["sog"] * math.sin(heading_rad) * elapsed_s
            ship["y"] += ship["sog"] * math.cos(heading_rad) * elapsed_s

    def clear(self) -> None:
        self._ships = {}
        self._last_step_at = None
