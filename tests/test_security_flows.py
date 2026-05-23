import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch


class AriaSecurityFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "aria_test.db"
        os.environ.update({
            "ARIA_DB_PATH": str(self.db_path),
            "APP_SECRET": "test-secret-that-is-long-enough-for-hmac",
            "EMAIL_SENDER": "sender@example.com",
            "EMAIL_PASSWORD": "app-password",
            "EMAIL_RECEIVER": "alerts@example.com",
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "587",
            "RECAPTCHA_USE_TEST_KEYS": "false",
            "RECAPTCHA_SITE_KEY": "site-key",
            "RECAPTCHA_SECRET_KEY": "secret-key",
        })
        from setup_db import create_tables

        create_tables(verbose=False)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_password_login_requires_verified_email(self):
        from auth import authenticate_user, hash_password, register_user_account
        from database.history_repository import register_user

        user_id = register_user_account(
            "Verified Co",
            "verified@example.com",
            "secure-pass-123",
            "Startup",
            100000,
        )
        self.assertIsNotNone(user_id)
        self.assertEqual(authenticate_user("verified@example.com", "secure-pass-123")["email"], "verified@example.com")

        unverified_id = register_user(
            "Unverified Co",
            "unverified@example.com",
            hash_password("secure-pass-456"),
            "Service",
            50000,
            email_verified=False,
        )
        self.assertIsNotNone(unverified_id)
        self.assertIsNone(authenticate_user("unverified@example.com", "secure-pass-456"))

    def test_otp_is_hashed_consumed_and_attempt_limited(self):
        from database.history_repository import get_latest_email_verification
        from verification import create_email_verification, verify_email_otp

        verification = create_email_verification("new@example.com")
        row = get_latest_email_verification("new@example.com", active_only=True)
        self.assertIsNotNone(row)
        self.assertNotEqual(row["otp_hash"], verification["otp_code"])
        self.assertEqual(len(verification["otp_code"]), 6)

        success = verify_email_otp("new@example.com", verification["otp_code"])
        self.assertTrue(success["success"])
        self.assertIsNone(get_latest_email_verification("new@example.com", active_only=True))

        second = create_email_verification("tries@example.com")
        for _ in range(4):
            result = verify_email_otp("tries@example.com", "000000")
            self.assertFalse(result["success"])
        final_result = verify_email_otp("tries@example.com", "000000")
        self.assertFalse(final_result["success"])
        self.assertIn("Too many", final_result["message"])
        self.assertIsNone(get_latest_email_verification("tries@example.com", active_only=True))
        self.assertFalse(verify_email_otp("tries@example.com", second["otp_code"])["success"])

    def test_expired_otp_is_rejected(self):
        from database.history_repository import (
            create_email_verification_record,
            get_latest_email_verification,
        )
        from verification import _hash_otp, verify_email_otp

        expired_at = (
            datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
        ).strftime("%Y-%m-%d %H:%M:%S")
        create_email_verification_record(
            "expired@example.com",
            _hash_otp("expired@example.com", "123456", "registration"),
            "registration",
            expired_at,
        )
        result = verify_email_otp("expired@example.com", "123456")
        self.assertFalse(result["success"])
        self.assertIn("expired", result["message"].lower())
        self.assertIsNone(get_latest_email_verification("expired@example.com", active_only=True))

    def test_resend_invalidates_older_otp(self):
        from database.db_connection import get_connection
        from database.history_repository import get_latest_email_verification
        from verification import create_email_verification, verify_email_otp

        first = create_email_verification("resend@example.com")
        old_created_at = (
            datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=2)
        ).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE email_verification_codes SET created_at = ? WHERE email = ?",
                (old_created_at, "resend@example.com"),
            )
            conn.commit()
        finally:
            conn.close()

        second = create_email_verification("resend@example.com")
        self.assertFalse(verify_email_otp("resend@example.com", first["otp_code"])["success"])
        self.assertTrue(verify_email_otp("resend@example.com", second["otp_code"])["success"])
        self.assertIsNone(get_latest_email_verification("resend@example.com", active_only=True))

    def test_password_reset_requires_otp_and_updates_hash(self):
        from auth import authenticate_user, register_user_account, reset_user_password
        from verification import create_email_verification, verify_email_otp

        register_user_account(
            "Reset Co",
            "reset@example.com",
            "old-pass-123",
            "Service",
            75000,
        )
        verification = create_email_verification("reset@example.com", purpose="password_reset")

        self.assertFalse(reset_user_password("missing@example.com", "new-pass-123"))
        self.assertTrue(verify_email_otp("reset@example.com", verification["otp_code"], purpose="password_reset")["success"])
        self.assertTrue(reset_user_password("reset@example.com", "new-pass-123"))
        self.assertIsNone(authenticate_user("reset@example.com", "old-pass-123"))
        self.assertEqual(authenticate_user("reset@example.com", "new-pass-123")["email"], "reset@example.com")

    def test_report_email_uses_registered_recipient_not_alert_receiver(self):
        from notifications import email_service

        sent_messages = []

        def capture(msg, settings):
            sent_messages.append(msg)

        with patch.object(email_service, "_send_message", side_effect=capture):
            email_service.send_report_email(
                recipient_email="user@example.com",
                report_text="risk report",
                summary={"risk_level": "Low", "risk_score": 12, "revenue": 100, "expenses": 50},
                report_id=42,
            )

        self.assertEqual(sent_messages[0]["To"], "user@example.com")
        self.assertNotEqual(sent_messages[0]["To"], os.environ["EMAIL_RECEIVER"])

    def test_recaptcha_verifier_success_and_failure(self):
        from verification import verify_recaptcha_token

        with patch(
            "verification._post_recaptcha",
            return_value={"success": True, "hostname": "example.streamlit.app"},
        ) as post:
            result = verify_recaptcha_token("token", remoteip="127.0.0.1")
        self.assertTrue(result["success"])
        self.assertEqual(post.call_args.args[0]["secret"], "secret-key")

        with patch(
            "verification._post_recaptcha",
            return_value={"success": False, "error-codes": ["timeout-or-duplicate"]},
        ):
            result = verify_recaptcha_token("token")
        self.assertFalse(result["success"])
        self.assertIn("timeout-or-duplicate", result["error_codes"])

    def test_development_recaptcha_uses_google_v2_test_keys(self):
        with patch.dict(os.environ, {
            "APP_ENV": "development",
            "RECAPTCHA_USE_TEST_KEYS": "true",
            "RECAPTCHA_SITE_KEY": "bad-local-key",
            "RECAPTCHA_SECRET_KEY": "bad-local-secret",
        }, clear=False):
            from config import (
                RECAPTCHA_V2_TEST_SECRET_KEY,
                RECAPTCHA_V2_TEST_SITE_KEY,
                get_settings,
            )

            settings = get_settings()
            self.assertTrue(settings.recaptcha_using_test_keys)
            self.assertEqual(settings.recaptcha_site_key, RECAPTCHA_V2_TEST_SITE_KEY)
            self.assertEqual(settings.recaptcha_secret_key, RECAPTCHA_V2_TEST_SECRET_KEY)

    def test_local_verification_token_only_valid_in_dev_mode(self):
        from verification import verify_recaptcha_token

        with patch.dict(os.environ, {
            "APP_ENV": "development",
            "RECAPTCHA_USE_TEST_KEYS": "true",
        }, clear=False):
            self.assertTrue(verify_recaptcha_token("local-dev-captcha-ok")["success"])
            self.assertFalse(verify_recaptcha_token("wrong-token")["success"])

    def test_complete_local_registration_flow(self):
        from auth import authenticate_user, hash_password, register_user_account_with_hash
        from database.history_repository import get_user_by_email
        from verification import create_email_verification, verify_email_otp, verify_recaptcha_token

        with patch.dict(os.environ, {"APP_ENV": "development", "RECAPTCHA_USE_TEST_KEYS": "true"}, clear=False):
            email = "local-flow@example.com"
            self.assertTrue(verify_recaptcha_token("local-dev-captcha-ok")["success"])
            verification = create_email_verification(email)

            wrong = verify_email_otp(email, "000000")
            self.assertFalse(wrong["success"])
            self.assertIn("Incorrect", wrong["message"])

            correct = verify_email_otp(email, verification["otp_code"])
            self.assertTrue(correct["success"])

            password_hash = hash_password("StrongPass123")
            user_id = register_user_account_with_hash(
                "Local Flow Co",
                email,
                password_hash,
                "Startup",
                100000,
            )
            self.assertIsNotNone(user_id)
            self.assertIsNotNone(get_user_by_email(email))
            self.assertEqual(authenticate_user(email, "StrongPass123")["email"], email)
            self.assertIsNone(register_user_account_with_hash(
                "Duplicate Co",
                email,
                password_hash,
                "Startup",
                100000,
            ))

    def test_get_user_by_id(self):
        from database.history_repository import register_user, get_user_by_id
        from auth import hash_password

        uid = register_user(
            "Test ID Co",
            "testid@example.com",
            hash_password("securepass123"),
            "Trading",
            120000.0,
            email_verified=True
        )
        self.assertIsNotNone(uid)
        user = get_user_by_id(uid)
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "testid@example.com")
        self.assertEqual(user["name"], "Test ID Co")
        self.assertEqual(user["business_type"], "Trading")
        self.assertEqual(user["starting_cash"], 120000.0)

    def test_download_txt_has_no_email_side_effect_hook(self):
        app_source = Path(__file__).resolve().parents[1] / "app.py"
        text = app_source.read_text(encoding="utf-8")
        self.assertNotIn("downloaded_complete_report", text)
        self.assertIn('st.button("Save Report and Send Email"', text)


if __name__ == "__main__":
    unittest.main()
