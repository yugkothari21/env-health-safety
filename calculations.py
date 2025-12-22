# calculations.py (polished & defensive)
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")
logger = logging.getLogger("calculations")

# ---------------- HEAT INDEX / COMFORT ---------------- #


def _to_float_safe(value) -> Optional[float]:
    """Try to convert value to float; return None if conversion fails."""
    try:
        if value is None:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def calculate_heat_index(temp_c: Optional[float], humidity: Optional[float]) -> Optional[float]:
    """
    Calculate Heat Index (feels-like temperature) from temperature (°C)
    and relative humidity (%) using the NOAA formula (computed in °F then converted back).
    Returns heat index in °C rounded to 2 decimals, or None if inputs are invalid.

    Notes:
    - NOAA formula is most reliable for T >= 80°F (~26.7°C) and humidity >= 40%,
      but we still compute a value for other inputs for project purposes.
    """
    try:
        T_c = _to_float_safe(temp_c)
        R = _to_float_safe(humidity)

        if T_c is None or R is None:
            return None

        # Convert °C to °F
        T = (T_c * 9.0 / 5.0) + 32.0

        # Guard: reasonable humidity range is 0-100
        if R < 0:
            R = 0.0
        if R > 100:
            R = 100.0

        # NOAA heat index polynomial (in °F)
        HI = (
            -42.379
            + 2.04901523 * T
            + 10.14333127 * R
            - 0.22475541 * T * R
            - 0.00683783 * T * T
            - 0.05481717 * R * R
            + 0.00122874 * T * T * R
            + 0.00085282 * T * R * R
            - 0.00000199 * T * T * R * R
        )

        # There are empirical adjustments for low humidity / high temp; ignore for simplicity.

        # Convert back to °C
        HI_c = (HI - 32.0) * 5.0 / 9.0
        return round(HI_c, 2)
    except Exception as e:
        logger.exception("calculate_heat_index error: %s", e)
        return None


def classify_heat(heat_index_c: Optional[float]) -> str:
    """
    Classify heat risk level based on heat index in °C.
    Returns "Safe", "Caution", "Danger", or "Unknown".
    """
    try:
        hi = _to_float_safe(heat_index_c)
        if hi is None:
            return "Unknown"
        if hi < 27.0:
            return "Safe"
        if hi < 32.0:
            return "Caution"
        return "Danger"
    except Exception as e:
        logger.exception("classify_heat error: %s", e)
        return "Unknown"


def get_comfort_message(heat_level: Optional[str]) -> str:
    """
    Return a human-readable comfort/safety message based on heat level.
    Accepts None safely.
    """
    try:
        if not heat_level:
            return "Heat data unavailable."
        level = str(heat_level)
        if level == "Safe":
            return "You are safe. Stay hydrated and enjoy your day."
        if level == "Caution":
            return "Avoid staying in direct sunlight for long periods."
        if level == "Danger":
            return "High risk of heat stress! Stay indoors and drink plenty of water."
        return "Heat data unavailable."
    except Exception as e:
        logger.exception("get_comfort_message error: %s", e)
        return "Heat data unavailable."


# ---------------- OXYGEN / ALTITUDE MODULE ---------------- #


def estimate_altitude_from_pressure(pressure_hpa: Optional[float]) -> Optional[float]:
    """
    Estimate altitude (in meters) from pressure (in hPa) using a standard atmosphere approximation.
    Returns altitude in meters rounded to 2 decimals, or None for invalid input.
    Formula: altitude = 44330 * (1 - (P / P0)^(1/5.255))
    """
    try:
        P = _to_float_safe(pressure_hpa)
        if P is None:
            return None
        if P <= 0:
            return None

        P0 = 1013.25  # sea-level standard pressure in hPa
        ratio = P / P0
        # Guard ratio domain
        if ratio <= 0:
            return None

        altitude = 44330.0 * (1.0 - (ratio ** (1.0 / 5.255)))
        return round(altitude, 2)
    except Exception as e:
        logger.exception("estimate_altitude_from_pressure error: %s", e)
        return None


def calculate_oxygen_availability(pressure_hpa: Optional[float]) -> Optional[float]:
    """
    Estimate oxygen availability (%) relative to sea level (21%) using a linear scaling.
    This is a simple educational approximation.
    """
    try:
        P = _to_float_safe(pressure_hpa)
        if P is None:
            return None

        P0 = 1013.25
        oxygen = 21.0 * (P / P0)
        return round(oxygen, 2)
    except Exception as e:
        logger.exception("calculate_oxygen_availability error: %s", e)
        return None


def classify_oxygen_level(oxygen_percent: Optional[float]) -> str:
    """
    Classify oxygen availability into safety levels.
    Returns "Safe", "Mild Risk", "High Risk", or "Unknown".
    """
    try:
        ox = _to_float_safe(oxygen_percent)
        if ox is None:
            return "Unknown"
        if ox >= 19.5:
            return "Safe"
        if ox >= 16.0:
            return "Mild Risk"
        return "High Risk"
    except Exception as e:
        logger.exception("classify_oxygen_level error: %s", e)
        return "Unknown"


def estimate_pressure_from_altitude(altitude_m: Optional[float]) -> Optional[float]:
    """
    Approximate pressure (hPa) from altitude (m) using standard atmosphere (inverse).
    Returns hPa rounded to 2 decimals, or None on invalid input.
    """
    try:
        h = _to_float_safe(altitude_m)
        if h is None:
            return None

        P0 = 1013.25
        term = 1.0 - (h / 44330.0)
        # Term must be > 0 to compute
        if term <= 0:
            return None

        ratio = term ** 5.255
        return round(P0 * ratio, 2)
    except Exception as e:
        logger.exception("estimate_pressure_from_altitude error: %s", e)
        return None


def find_safe_altitude_limit(start_alt_m: Optional[float], min_safe_oxygen: float = 16.0, max_alt_m: int = 6000) -> Optional[float]:
    """
    Starting from user's current altitude, estimate how high they can go
    while keeping oxygen >= min_safe_oxygen (%).
    Step search every 100 m by default.
    Returns last safe altitude in meters rounded to 2 decimals, or None on invalid input.
    """
    try:
        start = _to_float_safe(start_alt_m)
        if start is None:
            return None
        if start < 0:
            start = 0.0

        # Sanity boundaries
        max_alt = float(max_alt_m)
        step = 100.0
        current_alt = start
        last_safe_alt = start

        # Prevent infinite loops by limiting number of iterations
        max_iters = int((max_alt - start) / max(step, 1.0)) + 2
        iters = 0

        while current_alt <= max_alt and iters < max_iters:
            pressure = estimate_pressure_from_altitude(current_alt)
            if pressure is None:
                break
            oxygen = calculate_oxygen_availability(pressure)
            if oxygen is None:
                break
            try:
                if oxygen < float(min_safe_oxygen):
                    break
            except Exception:
                break
            last_safe_alt = current_alt
            current_alt += step
            iters += 1

        return round(last_safe_alt, 2)
    except Exception as e:
        logger.exception("find_safe_altitude_limit error: %s", e)
        return None

def personalized_min_oxygen(age, conditions):
    """
    Returns minimum safe oxygen % based on user profile.
    Educational risk-awareness logic.
    """
    base = 16.0

    condition_map = {
        "asthma": 17.5,
        "bronchitis": 18.0,
        "copd": 19.0,
    }

    for c in conditions:
        if c in condition_map:
            base = max(base, condition_map[c])

    if age is not None and age >= 60:
        base += 0.5

    return round(base, 2)



# ---------------- NOISE / SOUND MODULE ---------------- #


def calculate_noise_dose(noise_db: Optional[float], exposure_minutes: Optional[float]) -> Optional[float]:
    """
    Simplified noise dose estimate:
    - 85 dB -> 8 hours safe
    - every +3 dB halves safe time
    Dose% = (exposure_hours / safe_hours) * 100
    Returns rounded percent or None.
    """
    try:
        dB = _to_float_safe(noise_db)
        mins = _to_float_safe(exposure_minutes)
        if dB is None or mins is None:
            return None
        if mins < 0:
            mins = 0.0

        exposure_hours = mins / 60.0
        reference_db = 85.0
        reference_hours = 8.0

        if dB <= reference_db:
            safe_hours = reference_hours
        else:
            steps = (dB - reference_db) / 3.0
            # handle large steps gracefully
            try:
                safe_hours = reference_hours / (2 ** steps)
            except OverflowError:
                safe_hours = 0.0

        # guard against zero safe_hours
        if safe_hours <= 0:
            # if safe_hours is effectively zero, dose is extremely high; set a large number
            dose_percent = float("inf")
        else:
            dose_percent = (exposure_hours / safe_hours) * 100.0

        # If infinite dose, return a very large number to indicate severe risk
        if dose_percent == float("inf"):
            return 9999.0
        return round(dose_percent, 2)
    except Exception as e:
        logger.exception("calculate_noise_dose error: %s", e)
        return None


def classify_noise_level(noise_db: Optional[float], exposure_minutes: Optional[float]) -> str:
    """
    Classify noise exposure risk level using dose percentage and absolute levels.
    Returns "Safe", "Caution", "High Risk", or "Unknown".
    """
    try:
        dB = _to_float_safe(noise_db)
        mins = _to_float_safe(exposure_minutes)

        if dB is None or mins is None:
            return "Unknown"

        dose = calculate_noise_dose(dB, mins)
        if dose is None:
            return "Unknown"

        # Interpret dose:
        if dose < 50.0:
            return "Safe"
        if dose < 100.0:
            return "Caution"
        return "High Risk"
    except Exception as e:
        logger.exception("classify_noise_level error: %s", e)
        return "Unknown"


def get_noise_message(status: Optional[str]) -> str:
    """
    Human-friendly guidance based on noise status.
    """
    try:
        if not status:
            return "Noise exposure data is incomplete or unknown."
        s = str(status)
        if s == "Safe":
            return "Noise exposure is within safe limits."
        if s == "Caution":
            return "Prolonged exposure at this noise level may cause hearing strain. Consider breaks or protection."
        if s == "High Risk":
            return "High risk of hearing damage! Limit exposure and use hearing protection."
        return "Noise exposure data is incomplete or unknown."
    except Exception as e:
        logger.exception("get_noise_message error: %s", e)
        return "Noise exposure data is incomplete or unknown."
