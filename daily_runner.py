"""
daily_runner.py  –  Automated Daily Analysis
Runs complete financial analysis for ALL registered users/businesses.
Schedule this script daily (e.g., via cron or Windows Task Scheduler).

Usage:
    python daily_runner.py
"""

import sys
import os
import traceback
from contextlib import closing

# ── Path fix so imports resolve from ARIA root ──────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_connection import get_connection
from database.history_repository import (
    save_risk_report,
    save_ai_recommendation
)
from workflows.financial_engine import generate_financial_summary, project_30_day_risk
from models.orchestrator import generate_ai
from notifications.email_service import send_email_alert
from setup_db import create_tables


# ==============================
# HELPERS
# ==============================

def get_all_user_ids():
    """Fetches all user IDs from the users table."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            rows = cursor.fetchall()
            return [row[0] for row in rows] if rows else []
    except Exception:
        print("❌ Database error while fetching users:")
        traceback.print_exc()
        return []


# ==============================
# MAIN
# ==============================

def main():
    print("\nStarting Daily ARIA Multi-Business Analysis...\n")
    create_tables()

    success_count = 0
    failure_count = 0

    user_ids = get_all_user_ids()

    if not user_ids:
        print("No users found in database. Register a business first.")
        return

    print(f"Total Businesses Found: {len(user_ids)}")

    for user_id in user_ids:
        print(f"\nProcessing User ID: {user_id}")

        try:
            # ── Step 1 : Generate financial summary ──────────────────────
            summary = generate_financial_summary(user_id)

            if not summary or "risk_level" not in summary:
                print(f"Invalid summary for User {user_id}, skipping...")
                continue

            # ── Step 2 : Predictive projection ───────────────────────────
            try:
                prediction_label = project_30_day_risk(summary)
                prediction_text  = f"30-day projected risk: {prediction_label}"
            except Exception as proj_err:
                prediction_text = None
                print(f"Projection failed for User {user_id}: {proj_err}")

            # ── Step 3 : Save risk report ─────────────────────────────────
            report_id = None
            try:
                report_id = save_risk_report(
                    user_id       = user_id,
                    risk_score    = summary["risk_score"],
                    risk_level    = summary["risk_level"],
                    prediction    = prediction_text
                )
            except Exception as hist_err:
                print(f"Failed to save risk report for User {user_id}: {hist_err}")

            # ── Step 4 : Generate AI insight ─────────────────────────────
            ai_result = None
            try:
                ai_result = generate_ai(summary)
                # Save AI recommendation to database
                if (
                    report_id
                    and isinstance(ai_result, dict)
                    and ai_result.get("success")
                    and ai_result.get("analysis")
                ):
                    analysis        = ai_result["analysis"]
                    suggestion_text = (
                        f"Summary: {analysis.get('summary', '')}\n"
                        f"Key Risk: {analysis.get('key_risk', '')}\n"
                        f"Recommendation: {analysis.get('recommendation', '')}"
                    )
                    save_ai_recommendation(report_id, suggestion_text)
            except Exception as ai_err:
                print(f"AI generation failed for User {user_id}: {ai_err}")

            # ── Step 5 : Send High-risk email alert ───────────────────────
            if summary.get("risk_level") == "High":
                print(f"HIGH RISK DETECTED for User {user_id}")
                try:
                    send_email_alert(summary, ai_result)
                except Exception as email_err:
                    print(f"Email failed for User {user_id}: {email_err}")

            print(f"Analysis completed for User {user_id}")
            success_count += 1

        except Exception:
            print(f"Critical error for User {user_id}")
            traceback.print_exc()
            failure_count += 1

    print(
        f"\nDaily analysis done.  "
        f"Success: {success_count}  |  Failed: {failure_count}\n"
    )

    if failure_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
