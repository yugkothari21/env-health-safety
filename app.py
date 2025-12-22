# app.py — FINAL STABLE VERSION (Signup + Personalized Dashboard)

from flask import (
    Flask, jsonify, request, render_template,
    redirect, url_for, session
)
from flask_cors import CORS
import logging
from typing import Any, Optional

# -------------------------
# Imports: Services & Logic
# -------------------------
from services import get_weather, get_weather_by_coords
from calculations import (
    calculate_heat_index,
    classify_heat,
    get_comfort_message,
    estimate_altitude_from_pressure,
    calculate_oxygen_availability,
    classify_oxygen_level,
    find_safe_altitude_limit,
    calculate_noise_dose,
    classify_noise_level,
    get_noise_message,
    personalized_min_oxygen,
)

from models import init_db, add_user, get_user

# -------------------------
# App & Logging Setup
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
logger = logging.getLogger("ehs_web")

app = Flask(__name__)
app.secret_key = "ehs_secret_key"   # required for sessions
CORS(app)

init_db()

# -------------------------
# Utility Helpers
# -------------------------
def _as_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None

def _round(v: Optional[float], n: int = 2):
    return round(v, n) if v is not None else None

# -------------------------
# ROUTES
# -------------------------

# ---------- DASHBOARD ----------
@app.route("/")
def index():
    user_email = session.get("email")
    return render_template("index.html", email=user_email)

# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        try:
            name = request.form["name"]
            email = request.form["email"]
            age = int(request.form["age"])
            conditions = request.form.getlist("conditions")

            add_user(name, email, age, conditions)

            # store user email in session
            session["email"] = email

            return redirect(url_for("index"))

        except Exception as e:
            logger.exception("Signup error")
            return render_template(
                "signup.html",
                error="User already exists or invalid input"
            )

    return render_template("signup.html")

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---------- API: METRICS ----------
@app.route("/api/metrics", methods=["GET"])
def api_metrics():
    try:
        src = request.args.to_dict(flat=True)

        # ---- User from session ----
        email = session.get("email")
        user = get_user(email) if email else None

        if user:
            age = user[3]
            conditions = user[4].split(",") if user[4] else []
            min_safe_oxygen = personalized_min_oxygen(age, conditions)
        else:
            age = None
            conditions = []
            min_safe_oxygen = 16.0

        print("PERSONALIZATION CHECK →",
              "AGE:", age,
              "CONDITIONS:", conditions,
              "MIN_OXYGEN:", min_safe_oxygen)

        # ---- Location ----
        lat = _as_float(src.get("lat"))
        lon = _as_float(src.get("lon"))
        city = src.get("city", "Pune")

        # ---- Noise ----
        noise_db = _as_float(src.get("noise_db"))
        noise_minutes = _as_float(src.get("noise_minutes"))

        # ---- Weather ----
        if lat is not None and lon is not None:
            weather = get_weather_by_coords(lat, lon)
        else:
            weather = get_weather(city)

        if weather.get("error"):
            return jsonify(weather), 400

        temp = _as_float(weather["temperature"])
        humidity = _as_float(weather["humidity"])
        pressure = _as_float(weather["pressure"])

        # ---- Heat ----
        heat_index = calculate_heat_index(temp, humidity)
        heat_level = classify_heat(heat_index)
        comfort_message = get_comfort_message(heat_level)

        # ---- Oxygen & Altitude ----
        altitude = estimate_altitude_from_pressure(pressure)
        oxygen_percent = calculate_oxygen_availability(pressure)
        oxygen_status = classify_oxygen_level(oxygen_percent)

        max_safe_altitude = find_safe_altitude_limit(
            altitude,
            min_safe_oxygen=min_safe_oxygen
        )

        extra_safe_ascent = (
            _round(max_safe_altitude - altitude)
            if max_safe_altitude and altitude else None
        )

        # ---- Noise ----
        noise_dose = (
            calculate_noise_dose(noise_db, noise_minutes)
            if noise_db and noise_minutes else None
        )

        noise_status = classify_noise_level(noise_db, noise_minutes)
        noise_message = get_noise_message(noise_status)

        return jsonify({
            "email": email,
            "age": age,
            "conditions": conditions,
            "personal_min_oxygen": min_safe_oxygen,

            "city": city,
            "temperature": _round(temp),
            "humidity": _round(humidity),
            "pressure": _round(pressure),

            "heat_index": _round(heat_index),
            "heat_level": heat_level,
            "comfort_message": comfort_message,

            "current_altitude_m": _round(altitude),
            "oxygen_percent": _round(oxygen_percent),
            "oxygen_status": oxygen_status,
            "max_safe_altitude_m": _round(max_safe_altitude),
            "extra_safe_ascent_m": extra_safe_ascent,

            "noise_db": noise_db,
            "noise_minutes": noise_minutes,
            "noise_dose_percent": _round(noise_dose),
            "noise_status": noise_status,
            "noise_message": noise_message,
        })

    except Exception as e:
        logger.exception("API error")
        return jsonify({
            "error": "internal_error",
            "details": str(e)
        }), 500

# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    app.run()

