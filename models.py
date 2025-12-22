import sqlite3

DB = "users.db"

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            age INTEGER,
            conditions TEXT
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
