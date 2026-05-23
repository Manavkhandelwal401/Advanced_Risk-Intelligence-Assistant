import sqlite3

from config import get_settings


def get_connection():
    """
    Creates and returns a SQLite database connection.
    Row factory set so columns are accessible by name.
    """
    conn = sqlite3.connect(get_settings().db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # Safe concurrent access
    conn.execute("PRAGMA foreign_keys=ON")    # Enforce FK constraints
    return conn
