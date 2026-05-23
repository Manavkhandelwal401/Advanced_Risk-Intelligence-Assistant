"""
setup_db.py  –  Creates ARIA SQLite database tables.

Run once before launching the app:
    python setup_db.py

Tables (as defined in the project report – Chapter 3, Section 3.5):
  1. users             – business / user details
  2. financial_data    – uploaded financial records
  3. risk_report       – generated risk reports
  4. ai_recommendation – AI-generated recommendations
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_connection import get_connection


def _add_column_if_missing(cursor, table_name, existing_columns, column_name, definition):
    if column_name not in existing_columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
        existing_columns.add(column_name)


def create_tables(verbose=True):
    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------
    # TABLE 1 : users  (Section 3.5.1)
    # --------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    NOT NULL UNIQUE,
            password      TEXT    NOT NULL,
            business_type TEXT    NOT NULL,
            starting_cash REAL    NOT NULL DEFAULT 100000.0,
            email_verified INTEGER NOT NULL DEFAULT 0,
            verified_at   TIMESTAMP,
            wallpaper_theme TEXT DEFAULT 'None'
        )
    """)

    # --------------------------------------------------
    # TABLE 2 : financial_data  (Section 3.5.2)
    # --------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_data (
            data_id    INTEGER   PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER   NOT NULL,
            revenue    REAL      NOT NULL,
            expenses   REAL      NOT NULL,
            profit     REAL      GENERATED ALWAYS AS (revenue - expenses) STORED,
            orders     REAL      NOT NULL DEFAULT 0,
            extra_data TEXT,
            date       DATE      NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # --------------------------------------------------
    # TABLE 3 : risk_report  (Section 3.5.3)
    # --------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risk_report (
            report_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            risk_score     REAL    NOT NULL,
            risk_level     TEXT    NOT NULL,
            prediction     TEXT,
            report_text    TEXT,
            summary_json   TEXT,
            recommendation_json TEXT,
            email_recipient TEXT,
            email_status   TEXT DEFAULT 'not_sent',
            email_error    TEXT,
            generated_date DATE    DEFAULT (DATE('now')),
            generated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # --------------------------------------------------
    # TABLE 4 : ai_recommendation  (Section 3.5.4)
    # --------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_recommendation (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id         INTEGER NOT NULL,
            suggestion_text   TEXT    NOT NULL,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES risk_report(report_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_verification_codes (
            code_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT      NOT NULL,
            otp_hash    TEXT      NOT NULL,
            purpose     TEXT      NOT NULL DEFAULT 'registration',
            expires_at  TIMESTAMP NOT NULL,
            attempts    INTEGER   NOT NULL DEFAULT 0,
            consumed_at TIMESTAMP,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Lightweight migrations for databases created by earlier versions.
    cursor.execute("PRAGMA table_info(users)")
    user_columns = {row[1] for row in cursor.fetchall()}
    added_email_verified = "email_verified" not in user_columns
    _add_column_if_missing(cursor, "users", user_columns, "email_verified", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(cursor, "users", user_columns, "verified_at", "TIMESTAMP")
    _add_column_if_missing(cursor, "users", user_columns, "wallpaper_theme", "TEXT DEFAULT 'None'")
    if added_email_verified:
        cursor.execute("""
            UPDATE users
            SET email_verified = 1,
                verified_at = COALESCE(verified_at, CURRENT_TIMESTAMP)
            WHERE email_verified = 0
        """)

    cursor.execute("PRAGMA table_info(financial_data)")
    financial_columns = {row[1] for row in cursor.fetchall()}
    _add_column_if_missing(cursor, "financial_data", financial_columns, "orders", "REAL NOT NULL DEFAULT 0")
    _add_column_if_missing(cursor, "financial_data", financial_columns, "extra_data", "TEXT")

    cursor.execute("PRAGMA table_info(risk_report)")
    risk_columns = {row[1] for row in cursor.fetchall()}
    if "generated_at" not in risk_columns:
        cursor.execute("ALTER TABLE risk_report ADD COLUMN generated_at TIMESTAMP")
        cursor.execute("""
            UPDATE risk_report
            SET generated_at = COALESCE(generated_date, CURRENT_TIMESTAMP)
            WHERE generated_at IS NULL
        """)
        risk_columns.add("generated_at")

    _add_column_if_missing(cursor, "risk_report", risk_columns, "report_text", "TEXT")
    _add_column_if_missing(cursor, "risk_report", risk_columns, "summary_json", "TEXT")
    _add_column_if_missing(cursor, "risk_report", risk_columns, "recommendation_json", "TEXT")
    _add_column_if_missing(cursor, "risk_report", risk_columns, "email_recipient", "TEXT")
    _add_column_if_missing(cursor, "risk_report", risk_columns, "email_status", "TEXT DEFAULT 'not_sent'")
    _add_column_if_missing(cursor, "risk_report", risk_columns, "email_error", "TEXT")

    cursor.execute("PRAGMA table_info(ai_recommendation)")
    ai_columns = {row[1] for row in cursor.fetchall()}
    if "created_at" not in ai_columns:
        cursor.execute("ALTER TABLE ai_recommendation ADD COLUMN created_at TIMESTAMP")
        cursor.execute("""
            UPDATE ai_recommendation
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
        """)

    # Keep only the newest financial record per user/date, then enforce uniqueness.
    cursor.execute("""
        DELETE FROM financial_data
        WHERE data_id NOT IN (
            SELECT MAX(data_id)
            FROM financial_data
            GROUP BY user_id, date
        )
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_financial_data_user_date
        ON financial_data(user_id, date)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_verification_lookup
        ON email_verification_codes(email, purpose, consumed_at, created_at)
    """)

    conn.commit()
    conn.close()
    if verbose:
        print("All ARIA tables created / verified successfully.")


if __name__ == "__main__":
    create_tables()
