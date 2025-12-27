import sqlite3
from datetime import datetime

DB = "users.db"

def init_db():
    with sqlite3.connect(DB) as con:
        # =========================
        # User Table (EXISTING)
        # =========================
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            age INTEGER,
            conditions TEXT
        )
        """)

        # =========================
        # Hazard Reports Table (EXISTING)
        # =========================
        con.execute("""
        CREATE TABLE IF NOT EXISTS hazards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            description TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # =========================
        # Hazard Reports Extended Metadata (EXISTING EXTENSION)
        # =========================
        try: con.execute("ALTER TABLE hazards ADD COLUMN location TEXT")
        except sqlite3.OperationalError: pass

        try: con.execute("ALTER TABLE hazards ADD COLUMN latitude REAL")
        except sqlite3.OperationalError: pass

        try: con.execute("ALTER TABLE hazards ADD COLUMN longitude REAL")
        except sqlite3.OperationalError: pass

        try: con.execute("ALTER TABLE hazards ADD COLUMN severity TEXT")
        except sqlite3.OperationalError: pass

        try: con.execute("ALTER TABLE hazards ADD COLUMN status TEXT DEFAULT 'NEW'")
        except sqlite3.OperationalError: pass

        # =========================
        # 🆘 Emergency Contacts (NEW)
        # =========================
        con.execute("""
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            name TEXT,
            phone TEXT,
            email TEXT
        )
        """)

        # =========================
        # 🆘 SOS Events (NEW)
        # =========================
        con.execute("""
        CREATE TABLE IF NOT EXISTS sos_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            latitude REAL,
            longitude REAL,
            location TEXT,
            timestamp DATETIME,
            status TEXT DEFAULT 'ACTIVE'
        )
        """)

# =========================
# USER FUNCTIONS (EXISTING)
# =========================

def add_user(name, email, age, conditions):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO users (name, email, age, conditions) VALUES (?, ?, ?, ?)",
            (name, email, age, ",".join(conditions))
        )

def get_user(email):
    with sqlite3.connect(DB) as con:
        cur = con.execute("SELECT * FROM users WHERE email=?", (email,))
        return cur.fetchone()

# =========================
# HAZARD FUNCTIONS (EXISTING)
# =========================

def add_hazard(haz_type, description):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO hazards (type, description) VALUES (?, ?)",
            (haz_type, description)
        )

def add_hazard_extended(
    haz_type,
    description,
    location=None,
    latitude=None,
    longitude=None,
    severity="MODERATE"
):
    with sqlite3.connect(DB) as con:
        con.execute("""
        INSERT INTO hazards
        (type, description, location, latitude, longitude, severity, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            haz_type,
            description,
            location,
            latitude,
            longitude,
            severity,
            datetime.utcnow().isoformat()
        ))

def get_all_hazards():
    with sqlite3.connect(DB) as con:
        cur = con.execute("""
        SELECT id, type, description, location, latitude, longitude, severity, timestamp, status
        FROM hazards
        ORDER BY timestamp DESC
        """)
        return cur.fetchall()

def get_hazards_nearby(lat, lon, radius=0.05):
    with sqlite3.connect(DB) as con:
        cur = con.execute("""
        SELECT * FROM hazards
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND ABS(latitude - ?) < ?
          AND ABS(longitude - ?) < ?
        """, (lat, radius, lon, radius))
        return cur.fetchall()

# =========================
# 🆘 EMERGENCY CONTACTS (NEW)
# =========================

def add_emergency_contact(user_email, name, phone, email=None):
    with sqlite3.connect(DB) as con:
        con.execute("""
        INSERT INTO emergency_contacts (user_email, name, phone, email)
        VALUES (?, ?, ?, ?)
        """, (user_email, name, phone, email))

def get_emergency_contacts(user_email):
    with sqlite3.connect(DB) as con:
        cur = con.execute("""
        SELECT name, phone, email
        FROM emergency_contacts
        WHERE user_email = ?
        """, (user_email,))
        return cur.fetchall()

# =========================
# 🆘 SOS EVENTS (NEW)
# =========================

def create_sos_event(user_email, lat, lon, location=None):
    with sqlite3.connect(DB) as con:
        con.execute("""
        INSERT INTO sos_events
        (user_email, latitude, longitude, location, timestamp, status)
        VALUES (?, ?, ?, ?, ?, 'ACTIVE')
        """, (
            user_email,
            lat,
            lon,
            location,
            datetime.utcnow().isoformat()
        ))

def get_active_sos_nearby(lat, lon, radius=0.05):
    with sqlite3.connect(DB) as con:
        cur = con.execute("""
        SELECT * FROM sos_events
        WHERE status = 'ACTIVE'
          AND ABS(latitude - ?) < ?
          AND ABS(longitude - ?) < ?
        """, (lat, radius, lon, radius))
        return cur.fetchall()

def resolve_sos_event(sos_id):
    with sqlite3.connect(DB) as con:
        con.execute("""
        UPDATE sos_events
        SET status = 'RESOLVED'
        WHERE id = ?
        """, (sos_id,))
