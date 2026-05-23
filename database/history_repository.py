"""
history_repository.py
Handles database read/write operations for:
  - financial_data   (save & fetch uploaded records)
  - risk_report      (save generated risk reports, fetch history)
  - ai_recommendation (save AI suggestions)
  - users            (fetch user list, register user)
"""

import json
import math
import sqlite3
from datetime import datetime

from database.db_connection import get_connection


def _validate_financial_record(record):
    try:
        record_date = str(record["date"]).strip()
        datetime.strptime(record_date, "%Y-%m-%d")
        revenue = float(record["revenue"])
        expenses = float(record["expenses"])
        orders = float(record.get("orders", 0) or 0)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Financial records require date, revenue, and expenses.") from exc

    if not all(math.isfinite(value) for value in [revenue, expenses, orders]):
        raise ValueError("Revenue, expenses, and orders must be finite numbers.")
    if revenue < 0 or expenses < 0 or orders < 0:
        raise ValueError("Revenue, expenses, and orders cannot be negative.")

    extra_data = record.get("extra_data")
    if isinstance(extra_data, (dict, list)):
        extra_data = json.dumps(extra_data, ensure_ascii=False)
    elif extra_data is not None:
        extra_data = str(extra_data)

    return {
        "date": record_date,
        "revenue": revenue,
        "expenses": expenses,
        "orders": orders,
        "extra_data": extra_data,
    }


# ==============================
# USER OPERATIONS
# ==============================

def get_all_users():
    """Returns list of (user_id, name, business_type) for all users."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, name, business_type FROM users ORDER BY user_id ASC"
        )
        return cursor.fetchall()
    finally:
        conn.close()


def get_user_by_email(email):
    """Returns a user row including password hash for authentication."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                user_id,
                name,
                email,
                password,
                business_type,
                starting_cash,
                COALESCE(email_verified, 0) AS email_verified,
                verified_at,
                COALESCE(wallpaper_theme, 'None') AS wallpaper_theme
            FROM users
            WHERE LOWER(email) = LOWER(?)
        """, (email,))
        return cursor.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Returns a user row for session recovery."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                user_id,
                name,
                email,
                password,
                business_type,
                starting_cash,
                COALESCE(email_verified, 0) AS email_verified,
                verified_at,
                COALESCE(wallpaper_theme, 'None') AS wallpaper_theme
            FROM users
            WHERE user_id = ?
        """, (user_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def update_user_wallpaper(user_id, wallpaper_theme):
    """Updates a user's selected UI wallpaper theme."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET wallpaper_theme = ? WHERE user_id = ?",
            (wallpaper_theme, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def register_user(
    name,
    email,
    password_hash,
    business_type,
    starting_cash=100000.0,
    email_verified=True,
):
    """
    Registers a new user/business.
    Returns the new user_id, or None if email already exists.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (
                name, email, password, business_type, starting_cash,
                email_verified, verified_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE NULL END)
        """, (
            name.strip(),
            email.strip().lower(),
            password_hash,
            business_type,
            starting_cash,
            1 if email_verified else 0,
            1 if email_verified else 0,
        ))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def create_email_verification_record(email, otp_hash, purpose, expires_at):
    """Stores a new OTP hash and invalidates previous active OTPs for the email/purpose."""
    normalized_email = str(email).strip().lower()
    normalized_purpose = str(purpose or "registration").strip().lower()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE email_verification_codes
            SET consumed_at = CURRENT_TIMESTAMP
            WHERE LOWER(email) = LOWER(?)
              AND purpose = ?
              AND consumed_at IS NULL
        """, (normalized_email, normalized_purpose))
        cursor.execute("""
            INSERT INTO email_verification_codes (email, otp_hash, purpose, expires_at)
            VALUES (?, ?, ?, ?)
        """, (normalized_email, otp_hash, normalized_purpose, expires_at))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_latest_email_verification(email, purpose="registration", active_only=False):
    """Returns the newest OTP record for an email/purpose."""
    normalized_email = str(email).strip().lower()
    normalized_purpose = str(purpose or "registration").strip().lower()
    active_clause = "AND consumed_at IS NULL" if active_only else ""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT code_id, email, otp_hash, purpose, expires_at,
                   attempts, consumed_at, created_at
            FROM email_verification_codes
            WHERE LOWER(email) = LOWER(?)
              AND purpose = ?
              {active_clause}
            ORDER BY code_id DESC
            LIMIT 1
        """, (normalized_email, normalized_purpose))
        return cursor.fetchone()
    finally:
        conn.close()


def increment_email_verification_attempts(code_id):
    """Increments failed OTP attempts for a verification record."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE email_verification_codes
            SET attempts = attempts + 1
            WHERE code_id = ?
        """, (code_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def consume_email_verification_code(code_id):
    """Marks an OTP record as consumed."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE email_verification_codes
            SET consumed_at = CURRENT_TIMESTAMP
            WHERE code_id = ?
              AND consumed_at IS NULL
        """, (code_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def update_user_password_hash(user_id, password_hash):
    """Updates a user's stored password hash."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password = ? WHERE user_id = ?",
            (password_hash, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_user_starting_cash(user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT starting_cash FROM users WHERE user_id = ?", (user_id,)
        )
        row = cursor.fetchone()
        return float(row[0]) if row and row[0] is not None else 100000.0
    finally:
        conn.close()


# ==============================
# FINANCIAL DATA OPERATIONS
# ==============================

def get_existing_financial_dates(user_id):
    """Returns dates already stored for a user's financial dataset."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT date FROM financial_data WHERE user_id = ?",
            (user_id,),
        )
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()


def save_financial_records(user_id, records, replace_existing=False):
    """
    Bulk-inserts financial records from a CSV upload.
    records: list of dicts with keys: date, revenue, expenses
    Optional keys: orders, extra_data
    If replace_existing is True, dates already present for this user are updated.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        existing_dates = get_existing_financial_dates(user_id)

        inserted = 0
        updated = 0
        skipped = 0

        for record in records:
            record = _validate_financial_record(record)
            params = (
                user_id,
                record["revenue"],
                record["expenses"],
                record["orders"],
                record["extra_data"],
                record["date"],
            )
            date_exists = record["date"] in existing_dates
            if date_exists and not replace_existing:
                skipped += 1
                continue

            if replace_existing:
                cursor.execute("""
                    INSERT INTO financial_data (user_id, revenue, expenses, orders, extra_data, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, date) DO UPDATE SET
                        revenue = excluded.revenue,
                        expenses = excluded.expenses,
                        orders = excluded.orders,
                        extra_data = excluded.extra_data
                """, params)
                if date_exists:
                    updated += 1
                else:
                    inserted += 1
                    existing_dates.add(record["date"])
            else:
                cursor.execute("""
                    INSERT INTO financial_data (user_id, revenue, expenses, orders, extra_data, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, params)
                inserted += 1
                existing_dates.add(record["date"])

        conn.commit()
        return {
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "total_input": len(records),
        }
    finally:
        conn.close()


def get_financial_data(user_id):
    """Returns all financial records for a user, ordered by date."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, revenue, expenses, profit, orders, extra_data
            FROM financial_data
            WHERE user_id = ?
            ORDER BY date ASC
        """, (user_id,))
        rows = cursor.fetchall()
        return [
            {
                "date":     row["date"],
                "revenue":  float(row["revenue"]),
                "expenses": float(row["expenses"]),
                "profit":   float(row["profit"]) if row["profit"] is not None else 0.0,
                "orders":   float(row["orders"]) if "orders" in row.keys() and row["orders"] is not None else 0.0,
                "extra_data": row["extra_data"] if "extra_data" in row.keys() else None,
            }
            for row in rows
        ]
    finally:
        conn.close()


def delete_financial_data(user_id):
    """Deletes all financial records for a user (allows re-upload)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM financial_data WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


# ==============================
# RISK REPORT OPERATIONS
# ==============================

def save_risk_report(
    user_id,
    risk_score,
    risk_level,
    prediction=None,
    report_text=None,
    summary_json=None,
    recommendation_json=None,
    email_recipient=None,
    email_status="not_sent",
    email_error=None,
):
    """
    Saves a generated risk report.
    Returns the new report_id.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO risk_report (
                user_id, risk_score, risk_level, prediction, report_text,
                summary_json, recommendation_json, email_recipient,
                email_status, email_error, generated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            user_id,
            risk_score,
            risk_level,
            prediction,
            report_text,
            summary_json,
            recommendation_json,
            email_recipient,
            email_status,
            email_error,
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_risk_report_email_status(report_id, email_status, email_error=None):
    """Updates email delivery status for a saved report."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE risk_report
            SET email_status = ?, email_error = ?
            WHERE report_id = ?
        """, (email_status, email_error, report_id))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_risk_history(user_id):
    """
    Returns list of (generated_date, risk_score) tuples
    for graphing historical risk trend.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(generated_at, generated_date), risk_score
            FROM risk_report
            WHERE user_id = ?
            ORDER BY COALESCE(generated_at, generated_date) ASC
        """, (user_id,))
        return cursor.fetchall()
    finally:
        conn.close()


def get_risk_reports(user_id):
    """Returns saved risk reports for a user, newest first."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                report_id,
                risk_score,
                risk_level,
                prediction,
                report_text,
                summary_json,
                recommendation_json,
                email_recipient,
                COALESCE(email_status, 'not_sent') AS email_status,
                email_error,
                COALESCE(generated_at, generated_date) AS generated_at
            FROM risk_report
            WHERE user_id = ?
            ORDER BY COALESCE(generated_at, generated_date) DESC, report_id DESC
        """, (user_id,))
        return cursor.fetchall()
    finally:
        conn.close()


def get_platform_average_risk(user_id):
    """Returns the average risk score for the authenticated user's own history."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT AVG(risk_score) FROM risk_report WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        avg = row[0] if row and row[0] is not None else 0
        return round(avg, 2)
    finally:
        conn.close()


# ==============================
# AI RECOMMENDATION OPERATIONS
# ==============================

def save_ai_recommendation(report_id, suggestion_text):
    """Saves an AI-generated recommendation linked to a risk report."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_recommendation (report_id, suggestion_text, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (report_id, suggestion_text))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_recommendations_for_report(report_id):
    """Returns all AI recommendations for a specific risk report."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT suggestion_text FROM ai_recommendation
            WHERE report_id = ?
            ORDER BY recommendation_id ASC
        """, (report_id,))
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_ai_recommendations_for_user(user_id):
    """Returns all AI recommendations linked to a user's risk reports."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ar.recommendation_id,
                ar.report_id,
                ar.suggestion_text,
                COALESCE(ar.created_at, rr.generated_at, rr.generated_date) AS created_at,
                rr.risk_score,
                rr.risk_level
            FROM ai_recommendation ar
            JOIN risk_report rr ON rr.report_id = ar.report_id
            WHERE rr.user_id = ?
            ORDER BY COALESCE(ar.created_at, rr.generated_at, rr.generated_date) DESC,
                     ar.recommendation_id DESC
        """, (user_id,))
        return cursor.fetchall()
    finally:
        conn.close()
