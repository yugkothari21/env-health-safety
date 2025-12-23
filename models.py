import sqlite3

DB = "users.db"

def init_db():
    with sqlite3.connect(DB) as con:
        # User Table (Existing)
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            age INTEGER,
            conditions TEXT
        )
        """)
        
        # Hazard Reports Table (NEW)
        con.execute("""
        CREATE TABLE IF NOT EXISTS hazards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            description TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

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

# NEW FUNCTION
def add_hazard(haz_type, description):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO hazards (type, description) VALUES (?, ?)",
            (haz_type, description)
        )