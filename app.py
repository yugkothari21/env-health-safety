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
    add_hazard,
    add_hazard_extended,
    get_hazards_nearby,

    # 🆘 NEW IMPORTS
    add_emergency_contact,
    get_emergency_contacts,
    create_sos_event,
    get_active_sos_nearby
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

@app.route("/")
def index():
    return render_template("index.html", email=session.get("email"))

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

# -------------------------
# API: METRICS (EXTENDED)
# -------------------------
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

        if lat is not None and lon is not None:
            weather = get_weather_by_coords(lat, lon)
        else:
            weather = get_weather(city)

        temp = _as_float(weather["temperature"])
        humidity = _as_float(weather["humidity"])
        pressure = _as_float(weather["pressure"])

        heat_index = calculate_heat_index(temp, humidity)
        heat_level = classify_heat(heat_index)
        comfort_message = get_comfort_message(heat_level)

        altitude = estimate_altitude_from_pressure(pressure)
        oxygen_percent = calculate_oxygen_availability(pressure)
        oxygen_status = classify_oxygen_level(oxygen_percent)

        # 🔴 AREA RISK (HAZARDS + SOS)
        area_risk = "NORMAL"

        if lat and lon:
            if get_hazards_nearby(lat, lon) or get_active_sos_nearby(lat, lon):
                area_risk = "HIGH"

        return jsonify({
            "temperature": _round(temp),
            "humidity": _round(humidity),
            "pressure": _round(pressure),
            "heat_index": _round(heat_index),
            "heat_level": heat_level,
            "comfort_message": comfort_message,
            "current_altitude_m": _round(altitude),
            "oxygen_percent": _round(oxygen_percent),
            "oxygen_status": oxygen_status,
            "personal_min_oxygen": min_safe_oxygen,
            "area_risk": area_risk
        })

    except Exception as e:
        logger.exception("Metrics error")
        return jsonify({"error": str(e)}), 500

# -------------------------
# API: HAZARD REPORTING
# -------------------------
@app.route('/api/report_hazard', methods=['POST'])
def report_hazard():
    data = request.json
    haz_type = data.get('type')
    desc = data.get('description')
    location = data.get('location')
    lat = _as_float(data.get('lat'))
    lon = _as_float(data.get('lon'))

    severity = "HIGH" if haz_type.lower() in ["fire", "gas", "chemical"] else "MODERATE"

    add_hazard(haz_type, desc)
    add_hazard_extended(haz_type, desc, location, lat, lon, severity)

    return jsonify({"status": "success", "severity": severity})

# -------------------------
# 🆘 API: ADD EMERGENCY CONTACT
# -------------------------
@app.route("/api/add_emergency_contact", methods=["POST"])
def add_contact():
    data = request.json
    add_emergency_contact(
        session.get("email"),
        data["name"],
        data["phone"],
        data.get("email")
    )
    return jsonify({"status": "saved"})

# -------------------------
# 🆘 API: GET EMERGENCY CONTACTS
# -------------------------
@app.route("/api/get_emergency_contacts")
def get_contacts():
    contacts = get_emergency_contacts(session.get("email"))
    return jsonify(contacts)

# -------------------------
# 🆘 API: SOS TRIGGER
# -------------------------
@app.route("/api/sos", methods=["POST"])
def sos():
    data = request.json
    create_sos_event(
        session.get("email", "Anonymous"),
        _as_float(data["lat"]),
        _as_float(data["lon"]),
        data.get("location")
    )
    return jsonify({
        "status": "SOS_TRIGGERED",
        "message": "Emergency services & contacts alerted"
    })

# -------------------------
# API: AI SAFETY BOT
# -------------------------
@app.route('/api/chat', methods=['POST'])
def chat():
    msg = request.json.get("message", "").lower()
    if "fire" in msg:
        return jsonify({"reply": "🔥 FIRE: Evacuate immediately!"})
    if "medical" in msg:
        return jsonify({"reply": "🚑 MEDICAL: Call emergency services."})
    return jsonify({"reply": "Ask about Fire, Medical, Noise, Heat, Chemicals."})

# -------------------------
# API: PDF REPORT
# -------------------------
@app.route('/api/download_report')
def download_report():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, "EHS Safety Report", ln=1)
    buffer = io.BytesIO()
    buffer.write(pdf.output(dest='S').encode('latin-1'))
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="report.pdf")

if __name__ == "__main__":
    app.run(debug=True)
