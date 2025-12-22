# services.py (polished & defensive)
import logging
import os
import time
from typing import Any, Dict, Optional

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError

# Optional constant fallback (you can keep, but prefer setting OPENWEATHER_API_KEY env var)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "4b2048e21cf2a99adc5d4b18960112c1")

# Constants
OWM_BASE = "https://api.openweathermap.org/data/2.5/weather"
REQUEST_TIMEOUT = 6  # seconds per request
MAX_RETRIES = 2
RETRY_BACKOFF = 1.0  # seconds (multiplied each retry)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")
logger = logging.getLogger("services")

# Create a session for connection reuse
_session = requests.Session()


def _safe_get(url: str, params: Dict[str, Any], retries: int = MAX_RETRIES) -> Optional[requests.Response]:
    """
    Perform a GET with timeout and simple retry/backoff on transient errors.
    Returns requests.Response on success, or None on persistent failure.
    """
    backoff = RETRY_BACKOFF
    for attempt in range(0, retries + 1):
        try:
            resp = _session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            # If we get 429 (rate limit), treat as transient and retry with backoff
            if resp.status_code == 429 and attempt < retries:
                logger.warning("Rate limited by OpenWeather (429). Backing off %.1f sec (attempt %d/%d).", backoff, attempt + 1, retries)
                time.sleep(backoff)
                backoff *= 2
                continue
            return resp
        except (Timeout, ConnectionError) as e:
            logger.warning("Network error on request (attempt %d/%d): %s", attempt + 1, retries + 1, e)
            if attempt < retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None
        except RequestException as e:
            logger.exception("Unexpected requests exception: %s", e)
            return None
    return None


def _build_error(message: str, details: Optional[str] = None) -> Dict[str, Any]:
    payload = {"error": True, "message": message}
    if details:
        payload["details"] = details
    return payload


def _normalize_weather_dict(raw: Dict[str, Any], city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
    """
    Normalize the OpenWeather response into a consistent dict:
    { "error": False, "city": str, "temperature": float, "humidity": float, "pressure": float, "lat":..., "lon":... }
    If expected fields are missing, return an error dict.
    """
    if not isinstance(raw, dict):
        return _build_error("invalid_response", details="weather API returned non-dict")

    main = raw.get("main", {})
    if not main:
        return _build_error("missing_main", details="OpenWeather response missing 'main' block")

    temp = main.get("temp")
    hum = main.get("humidity")
    pres = main.get("pressure")

    # Try to coerce to floats/ints safely
    try:
        temp = None if temp is None else float(temp)
    except Exception:
        temp = None
    try:
        hum = None if hum is None else float(hum)
    except Exception:
        hum = None
    try:
        pres = None if pres is None else float(pres)
    except Exception:
        pres = None

    if temp is None or hum is None or pres is None:
        return _build_error("incomplete_weather_data", details=f"temp={temp},hum={hum},pres={pres}")

    # If the API response also includes coord data, prefer it for lat/lon
    coords = raw.get("coord") or {}
    rlat = coords.get("lat") if coords.get("lat") is not None else lat
    rlon = coords.get("lon") if coords.get("lon") is not None else lon

    normalized = {
        "error": False,
        "city": city or raw.get("name"),
        "temperature": temp,
        "humidity": hum,
        "pressure": pres,
    }
    if rlat is not None:
        try:
            normalized["lat"] = float(rlat)
        except Exception:
            pass
    if rlon is not None:
        try:
            normalized["lon"] = float(rlon)
        except Exception:
            pass

    return normalized


def get_weather(city: str = "Pune") -> Dict[str, Any]:
    """
    Get weather by city name. Returns a consistent dict.
    """
    if not OPENWEATHER_API_KEY:
        return _build_error("missing_api_key", "Set OPENWEATHER_API_KEY environment variable")

    if not city:
        return _build_error("invalid_city", "City name is empty")

    params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"}
    logger.info("get_weather: requesting city=%s", city)
    resp = _safe_get(OWM_BASE, params=params)

    if resp is None:
        return _build_error("network_error", "Failed to reach OpenWeather API")

    try:
        data = resp.json()
    except Exception as e:
        logger.exception("Failed to parse JSON from OpenWeather: %s", e)
        return _build_error("invalid_json", details=str(e))

    # Non-200 handling
    if resp.status_code != 200:
        msg = data.get("message") if isinstance(data, dict) else "OpenWeather returned error"
        return _build_error("api_error", f"{msg} (status {resp.status_code})")

    return _normalize_weather_dict(data, city=city)


def get_weather_by_coords(lat: Any, lon: Any) -> Dict[str, Any]:
    """
    Get weather by latitude and longitude. Returns a consistent dict.
    """
    if not OPENWEATHER_API_KEY:
        return _build_error("missing_api_key", "Set OPENWEATHER_API_KEY environment variable")

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except Exception:
        return _build_error("invalid_coords", "Latitude and longitude must be numeric")

    params = {"lat": lat_f, "lon": lon_f, "appid": OPENWEATHER_API_KEY, "units": "metric"}
    logger.info("get_weather_by_coords: requesting lat=%s lon=%s", lat_f, lon_f)
    resp = _safe_get(OWM_BASE, params=params)

    if resp is None:
        return _build_error("network_error", "Failed to reach OpenWeather API")

    try:
        data = resp.json()
    except Exception as e:
        logger.exception("Failed to parse JSON from OpenWeather: %s", e)
        return _build_error("invalid_json", details=str(e))

    if resp.status_code != 200:
        msg = data.get("message") if isinstance(data, dict) else "OpenWeather returned error"
        return _build_error("api_error", f"{msg} (status {resp.status_code})")

    return _normalize_weather_dict(data, lat=lat_f, lon=lon_f)
