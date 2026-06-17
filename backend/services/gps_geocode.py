"""Reverse geocoding helpers for GPS fleet (Nominatim with in-memory cache)."""
from __future__ import annotations

import logging
import math
import re
import time
from typing import Any

import httpx

logger = logging.getLogger("azmus.gps_geocode")

_CACHE: dict[tuple[int, int], tuple[float, dict[str, str]]] = {}
_CACHE_TTL_SEC = 300
_LAST_REQUEST_AT = 0.0
_MIN_INTERVAL_SEC = 1.1  # Nominatim usage policy


def _grid_key(lat: float, lng: float, precision: int = 2) -> tuple[int, int]:
    return (round(lat, precision), round(lng, precision))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_km(lat1, lon1, lat2, lon2) * 1000.0


def estimate_eta_hours(
    lat: float,
    lng: float,
    dest_lat: float | None,
    dest_lng: float | None,
    speed_kmh: float,
) -> float | None:
    if dest_lat is None or dest_lng is None:
        return None
    dist = haversine_km(lat, lng, dest_lat, dest_lng)
    if dist < 0.5:
        return 0.0
    effective_speed = max(speed_kmh, 20.0) if speed_kmh > 0 else 55.0
    return round(dist / effective_speed, 1)


def _normalize_place(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


# Common transliterations for Central Asia destinations
_CITY_ALIASES: dict[str, set[str]] = {
    "tashkent": {"tashkent", "toshkent", "ташкент"},
    "samarkand": {"samarkand", "samarqand"},
    "almaty": {"almaty", "alma-ata"},
}


def _city_variants(name: str) -> set[str]:
    n = _normalize_place(name)
    variants = {n}
    for canonical, aliases in _CITY_ALIASES.items():
        if n in aliases or canonical in n or n in canonical:
            variants |= aliases | {canonical}
    return variants


def city_matches_destination(city: str, destination: str) -> bool:
    if not city or not destination:
        return False
    city_vars = _city_variants(city)
    dest = _normalize_place(destination)
    if any(v in dest or dest in v for v in city_vars):
        return True
    return any(part in dest for v in city_vars for part in v.split() if len(part) > 3)


# Known destination coordinates for ETA when geocoding is unavailable
DESTINATION_COORDS: dict[str, tuple[float, float]] = {
    "tashkent": (41.2995, 69.2401),
    "toshkent": (41.2995, 69.2401),
    "samarkand": (39.6542, 66.9597),
    "bukhara": (39.7747, 64.4286),
    "andijan": (40.7821, 72.3442),
    "fergana": (40.3842, 71.7843),
    "namangan": (40.9983, 71.6726),
    "nukus": (42.4531, 59.6103),
    "almaty": (43.2220, 76.8512),
    "astana": (51.1694, 71.4491),
    "shymkent": (42.3417, 69.5901),
    "moscow": (55.7558, 37.6173),
    "istanbul": (41.0082, 28.9784),
}


def coords_for_destination(destination: str) -> tuple[float, float] | None:
    key = _normalize_place(destination)
    for name, coords in DESTINATION_COORDS.items():
        if name in key or key in name:
            return coords
    return None


def reverse_geocode(lat: float, lng: float) -> dict[str, str]:
    """Return {city, country, country_code} — cached ~5 min per grid cell."""
    key = _grid_key(lat, lng)
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]

    global _LAST_REQUEST_AT
    wait = _MIN_INTERVAL_SEC - (now - _LAST_REQUEST_AT)
    if wait > 0:
        time.sleep(wait)

    result = {"city": "", "country": "", "country_code": ""}
    try:
        _LAST_REQUEST_AT = time.time()
        with httpx.Client(timeout=8) as client:
            resp = client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lng, "format": "json", "zoom": 10},
                headers={"User-Agent": "AzmusERP/2.0 GPS Fleet"},
            )
            if resp.status_code == 200:
                data: dict[str, Any] = resp.json()
                addr = data.get("address") or {}
                result["city"] = (
                    addr.get("city")
                    or addr.get("town")
                    or addr.get("village")
                    or addr.get("county")
                    or addr.get("state")
                    or ""
                )
                result["country"] = addr.get("country") or ""
                result["country_code"] = (addr.get("country_code") or "").upper()
    except Exception as exc:
        logger.debug("reverse geocode failed: %s", exc)

    _CACHE[key] = (time.time(), result)
    return result
