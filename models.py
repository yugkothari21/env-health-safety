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
        # Hazard Reports Extended Metadata (NEW)
        # =========================
        # We keep the original hazards table intact
        # and EXTEND it safely with new columns if missing

        try:
            con.execute("ALTER TABLE hazards ADD COLUMN location TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            con.execute("ALTER TABLE hazards ADD COLUMN latitude REAL")
        except sqlite3.OperationalError:
            pass

        try:
            con.execute("ALTER TABLE hazards ADD COLUMN longitude REAL")
        except sqlite3.OperationalError:
            pass

        try:
            con.execute("ALTER TABLE hazards ADD COLUMN severity TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            con.execute("ALTER TABLE hazards ADD COLUMN status TEXT DEFAULT 'NEW'")
        except sqlite3.OperationalError:
            pass


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


# =========================
# HAZARD FUNCTIONS (NEW)
# =========================

def add_hazard_extended(
    haz_type,
    description,
    location=None,
    latitude=None,
    longitude=None,
    severity="MODERATE"
):
    """
    Stores a complete hazard report with location and severity.
    This DOES NOT replace existing add_hazard().
    """
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
    """
    Returns all reported hazards.
    Useful for admin dashboards and area risk evaluation.
    """
    with sqlite3.connect(DB) as con:
        cur = con.execute("""
        SELECT id, type, description, location, latitude, longitude, severity, timestamp, status
        FROM hazards
        ORDER BY timestamp DESC
        """)
        return cur.fetchall()


def get_hazards_nearby(lat, lon, radius=0.05):
    """
    Finds hazards within a geographic radius.
    Used to mark an area as HIGH RISK.
    """
    with sqlite3.connect(DB) as con:
        cur = con.execute("""
        SELECT * FROM hazards
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND ABS(latitude - ?) < ?
          AND ABS(longitude - ?) < ?
        """, (lat, radius, lon, radius))
        return cur.fetchall()
