"""Trimble Maps Single Search geocoding adapter (SPEC-017)."""

from __future__ import annotations

import os
import time
from collections import deque
from threading import Lock
from urllib.parse import quote

import httpx

from backend.schemas.location import GeocodeRequest

TRIMBLE_SEARCH_URL = "https://singlesearch.alk.com/{region}/api/search"
DEFAULT_REGION = "na"
GEOCODE_NOT_FOUND_MESSAGE = "Could not find coordinates for this address"

# Light rate limit: 250/min per process (Trimble quota).
_RATE_LIMIT_PER_MINUTE = 250
_rate_timestamps: deque[float] = deque()
_rate_lock = Lock()

# Session-scoped cache keyed by normalized address tuple.
_geocode_cache: dict[tuple[str, str, str, str], dict] = {}
_cache_lock = Lock()


class GeocodeNotFoundError(Exception):
    """Raised when Trimble returns no usable match."""


class GeocodeServiceUnavailableError(Exception):
    """Raised when the API key is missing or the provider is unreachable."""


def _normalize_key(request: GeocodeRequest) -> tuple[str, str, str, str]:
    return (
        request.address.strip().casefold(),
        request.city.strip().casefold(),
        request.state.strip().casefold(),
        str(request.zip).strip(),
    )


def _check_rate_limit() -> None:
    now = time.monotonic()
    with _rate_lock:
        while _rate_timestamps and now - _rate_timestamps[0] > 60:
            _rate_timestamps.popleft()
        if len(_rate_timestamps) >= _RATE_LIMIT_PER_MINUTE:
            raise GeocodeServiceUnavailableError("Geocoding rate limit exceeded; try again shortly")
        _rate_timestamps.append(now)


def _build_query(request: GeocodeRequest) -> str:
    return f"{request.address.strip()}, {request.city.strip()}, {request.state.strip()} {request.zip.strip()}"


def geocode_address(request: GeocodeRequest) -> dict:
    """Forward-geocode an address via Trimble Single Search.

    Returns a dict with latitude, longitude, formatted_address, provider.
    Raises GeocodeNotFoundError or GeocodeServiceUnavailableError on failure.
    """
    cache_key = _normalize_key(request)
    with _cache_lock:
        cached = _geocode_cache.get(cache_key)
    if cached is not None:
        return dict(cached)

    api_key = os.getenv("TRIMBLE_MAPS_API_KEY", "").strip()
    if not api_key:
        raise GeocodeServiceUnavailableError(
            "Geocoding is not configured on this server; enter coordinates manually"
        )

    _check_rate_limit()

    region = os.getenv("TRIMBLE_SINGLESEARCH_REGION", DEFAULT_REGION).strip() or DEFAULT_REGION
    url = TRIMBLE_SEARCH_URL.format(region=region)
    query = _build_query(request)
    params = {
        "query": query,
        "maxResults": "1",
        "countries": "US",
        "states": request.state.strip().upper(),
        "excludeResultsFor": "POI,POIType",
    }
    headers = {"Authorization": api_key}

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        raise GeocodeServiceUnavailableError("Geocoding service is temporarily unavailable") from exc

    if response.status_code != 200:
        raise GeocodeNotFoundError(GEOCODE_NOT_FOUND_MESSAGE)

    payload = response.json()
    if payload.get("Err", 1) != 0:
        raise GeocodeNotFoundError(GEOCODE_NOT_FOUND_MESSAGE)

    locations = payload.get("Locations") or []
    if not locations:
        raise GeocodeNotFoundError(GEOCODE_NOT_FOUND_MESSAGE)

    loc = locations[0]
    coords = loc.get("Coords") or {}
    try:
        latitude = float(coords["Lat"])
        longitude = float(coords["Lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodeNotFoundError(GEOCODE_NOT_FOUND_MESSAGE) from exc

    result = {
        "latitude": latitude,
        "longitude": longitude,
        "formatted_address": loc.get("ShortString"),
        "provider": "trimble-single-search",
    }

    with _cache_lock:
        _geocode_cache[cache_key] = dict(result)
    return result
