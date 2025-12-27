from flask import (
    Flask, jsonify, request, render_template,
    redirect, url_for, session, send_file
)
from flask_cors import CORS
import logging
from typing import Any, Optional
import io
import datetime
from fpdf import FPDF

# -------------------------
# Imports: Services & Logic
# -------------------------
from services import get_weather, get_weather_by_coords
from calculations import (
    calculate_heat_index, classify_heat, get_comfort_message,
    estimate_altitude_from_pressure, calculate_oxygen_availability,
    classify_oxygen_level, find_safe_altitude_limit,
    calculate_noise_dose, classify_noise_level, get_noise_message,
    personalized_min_oxygen,
)

# -------------------------
# Imports: Database Models
# -------------------------
from models import (
    init_db,
    add_user,
    get_user,
    add_hazard,                 # EXISTING
    add_hazard_extended,        # NEW
    get_hazards_nearby           # NEW
)

# -------------------------
# App & Logging Setup
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
logger = logging.getLogger("ehs_web")

app = Flask(__name__)
app.secret_key = "ehs_secret_key"
CORS(app)

# Initialize DB
init_db()

# -------------------------
# Utility Helpers (EXISTING)
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

@app.route("/")
def index():
    user_email = session.get("email")
    return render_template("index.html", email=user_email)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        try:
            name = request.form["name"]
            email = request.form["email"]
            age = int(request.form["age"])
            conditions = request.form.getlist("conditions")
            add_user(name, email, age, conditions)
            session["email"] = email
            return redirect(url_for("index"))
        except Exception:
            logger.exception("Signup error")
            return render_template("signup.html", error="User already exists or invalid input")
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---------- API: METRICS (EXTENDED, NOTHING REMOVED) ----------
@app.route("/api/metrics", methods=["GET"])
def api_metrics():
    try:
        src = request.args.to_dict(flat=True)
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

        lat = _as_float(src.get("lat"))
        lon = _as_float(src.get("lon"))
        city = src.get("city", "Pune")
        noise_db = _as_float(src.get("noise_db"))
        noise_minutes = _as_float(src.get("noise_minutes"))

        if lat is not None and lon is not None:
            weather = get_weather_by_coords(lat, lon)
        else:
            weather = get_weather(city)

        if weather.get("error"):
            return jsonify(weather), 400

        temp = _as_float(weather["temperature"])
        humidity = _as_float(weather["humidity"])
        pressure = _as_float(weather["pressure"])

        heat_index = calculate_heat_index(temp, humidity)
        heat_level = classify_heat(heat_index)
        comfort_message = get_comfort_message(heat_level)

        altitude = estimate_altitude_from_pressure(pressure)
        oxygen_percent = calculate_oxygen_availability(pressure)
        oxygen_status = classify_oxygen_level(oxygen_percent)

        max_safe_altitude = find_safe_altitude_limit(
            altitude, min_safe_oxygen=min_safe_oxygen
        )

        extra_safe_ascent = (
            _round(max_safe_altitude - altitude) if max_safe_altitude and altitude else None
        )

        noise_dose = (
            calculate_noise_dose(noise_db, noise_minutes) if noise_db and noise_minutes else None
        )
        noise_status = classify_noise_level(noise_db, noise_minutes)
        noise_message = get_noise_message(noise_status)

        # -------------------------
        # NEW: AREA RISK DETECTION
        # -------------------------
        area_risk = "NORMAL"
        if lat is not None and lon is not None:
            nearby_hazards = get_hazards_nearby(lat, lon)
            if nearby_hazards:
                area_risk = "HIGH"

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

            # NEW
            "area_risk": area_risk
        })

    except Exception as e:
        logger.exception("API error")
        return jsonify({"error": "internal_error", "details": str(e)}), 500

# ---------- API: HAZARD REPORTING (EXTENDED) ----------
@app.route('/api/report_hazard', methods=['POST'])
def report_hazard():
    try:
        data = request.json
        haz_type = data.get('type')
        desc = data.get('description')
        location = data.get('location')
        lat = _as_float(data.get('lat'))
        lon = _as_float(data.get('lon'))

        if not haz_type or not desc:
            return jsonify({"status": "error", "message": "Missing fields"}), 400

        critical = ["fire", "gas", "chemical"]
        severity = "HIGH" if haz_type.lower() in critical else "MODERATE"

        # EXISTING FUNCTION (unchanged)
        add_hazard(haz_type, desc)

        # NEW EXTENDED STORAGE
        add_hazard_extended(
            haz_type,
            desc,
            location=location,
            latitude=lat,
            longitude=lon,
            severity=severity
        )

        return jsonify({
            "status": "success",
            "message": "Hazard reported successfully",
            "severity": severity,
            "escalated": severity == "HIGH",
            "report": {
                "type": haz_type,
                "description": desc,
                "location": location,
                "latitude": lat,
                "longitude": lon
            }
        })

    except Exception as e:
        logger.exception("Hazard report error")
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------- API: AI SAFETY BOT (UNCHANGED) ----------
@app.route('/api/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message', '').lower()

    if "fire" in user_msg or "smoke" in user_msg:
        reply = "🔥 FIRE EMERGENCY: Pull the alarm. Evacuate immediately via stairs."
    elif "faint" in user_msg or "medical" in user_msg:
        reply = "🚑 MEDICAL ALERT: Provide water if conscious. Call emergency services."
    elif "noise" in user_msg:
        reply = "🔊 NOISE SAFETY: Above 85dB, hearing protection is required."
    elif "chemical" in user_msg or "spill" in user_msg:
        reply = "🧪 CHEMICAL HAZARD: Evacuate area. Refer to MSDS."
    elif "heat" in user_msg:
        reply = "☀️ HEAT STRESS: Move to shade. Hydrate immediately."
    else:
        reply = "I am the EHS Safety Bot. Ask about Fire, Medical, Noise, Chemicals, or Heat safety."

    return jsonify({"reply": reply})

# ---------- API: PDF REPORT (UNCHANGED) ----------
@app.route('/api/download_report')
def download_report():
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "EHS Nexus - Site Safety Audit", ln=1, align='C')
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 10, f"Generated: {datetime.datetime.now()}", ln=1, align='C')

        buffer = io.BytesIO()
        buffer.write(pdf.output(dest='S').encode('latin-1'))
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name="EHS_Report.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.exception("PDF error")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
