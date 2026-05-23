"""
Registration verification helpers for ARIA.

OTP values are never stored directly. ARIA stores an HMAC of email, purpose,
and OTP code using APP_SECRET, so a leaked SQLite file cannot reveal active OTPs.
"""

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib import error, parse, request

from config import require_app_secret, require_recaptcha_config
from database.history_repository import (
    consume_email_verification_code,
    create_email_verification_record,
    get_latest_email_verification,
    increment_email_verification_attempts,
)


OTP_TTL_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _format_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse_timestamp(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _normalize_email(email: str) -> str:
    normalized = str(email or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise ValueError("Enter a valid email address before requesting OTP.")
    return normalized


def _normalize_purpose(purpose: str) -> str:
    return str(purpose or "registration").strip().lower()


def _hash_otp(email: str, otp_code: str, purpose: str) -> str:
    settings = require_app_secret()
    payload = f"{_normalize_email(email)}|{_normalize_purpose(purpose)}|{str(otp_code).strip()}"
    return hmac.new(
        settings.app_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_email_verification(email: str, purpose: str = "registration") -> dict:
    """
    Creates and stores a new OTP hash.

    Returns the plaintext OTP only to the caller so it can be sent immediately
    by the email service. The database receives only the HMAC hash.
    """
    normalized_email = _normalize_email(email)
    normalized_purpose = _normalize_purpose(purpose)
    latest = get_latest_email_verification(normalized_email, normalized_purpose)
    latest_created_at = _parse_timestamp(latest["created_at"]) if latest else None
    if latest_created_at:
        age_seconds = (_utcnow() - latest_created_at).total_seconds()
        if age_seconds < OTP_RESEND_COOLDOWN_SECONDS:
            wait_seconds = max(1, int(OTP_RESEND_COOLDOWN_SECONDS - age_seconds))
            raise RuntimeError(f"Please wait {wait_seconds} seconds before requesting another OTP.")

    otp_code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = _utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    code_id = create_email_verification_record(
        normalized_email,
        _hash_otp(normalized_email, otp_code, normalized_purpose),
        normalized_purpose,
        _format_timestamp(expires_at),
    )
    return {
        "email": normalized_email,
        "otp_code": otp_code,
        "code_id": code_id,
        "purpose": normalized_purpose,
        "expires_at": _format_timestamp(expires_at),
    }


def verify_email_otp(email: str, code: str, purpose: str = "registration") -> dict:
    """Verifies a submitted OTP against the newest active OTP record."""
    normalized_email = _normalize_email(email)
    normalized_purpose = _normalize_purpose(purpose)
    otp_code = str(code or "").strip()
    if len(otp_code) != 6 or not otp_code.isdigit():
        return {"success": False, "message": "Enter the 6-digit OTP sent to your email."}

    row = get_latest_email_verification(normalized_email, normalized_purpose, active_only=True)
    if not row:
        return {"success": False, "message": "No active OTP found. Request a new verification code."}

    code_id = row["code_id"]
    attempts = int(row["attempts"] or 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        consume_email_verification_code(code_id)
        return {"success": False, "message": "Too many incorrect OTP attempts. Request a new code."}

    expires_at = _parse_timestamp(row["expires_at"])
    if not expires_at or expires_at < _utcnow():
        consume_email_verification_code(code_id)
        return {"success": False, "message": "OTP expired. Request a new verification code."}

    submitted_hash = _hash_otp(normalized_email, otp_code, normalized_purpose)
    if not hmac.compare_digest(submitted_hash, row["otp_hash"]):
        increment_email_verification_attempts(code_id)
        if attempts + 1 >= OTP_MAX_ATTEMPTS:
            consume_email_verification_code(code_id)
            return {"success": False, "message": "Too many incorrect OTP attempts. Request a new code."}
        return {"success": False, "message": "Incorrect OTP. Please check the code and try again."}

    consume_email_verification_code(code_id)
    return {"success": True, "message": "Email verified successfully."}


def verify_recaptcha_token(token: str, remoteip: str | None = None) -> dict:
    """Verifies a Google reCAPTCHA v2 token through Google's server-side API."""
    settings = require_recaptcha_config()
    token = str(token or "").strip()
    if not token:
        return {"success": False, "message": "Complete the verification check before continuing."}

    if settings.recaptcha_using_test_keys:
        if token == "local-dev-captcha-ok":
            return {
                "success": True,
                "message": "Local verification completed.",
                "hostname": "localhost",
            }
        return {
            "success": False,
            "message": "Complete the local verification check before continuing.",
        }

    payload = {
        "secret": settings.recaptcha_secret_key,
        "response": token,
    }
    if remoteip:
        payload["remoteip"] = remoteip

    try:
        result = _post_recaptcha(payload)
    except (OSError, TimeoutError, error.URLError) as exc:
        return {"success": False, "message": f"Could not verify reCAPTCHA: {exc}"}
    except ValueError:
        return {"success": False, "message": "Invalid reCAPTCHA verification response."}

    if result.get("success"):
        return {
            "success": True,
            "message": "reCAPTCHA verified successfully.",
            "hostname": result.get("hostname"),
        }

    error_codes = result.get("error-codes", [])
    friendly_messages = {
        "missing-input-secret": "The reCAPTCHA secret key is missing on the server.",
        "invalid-input-secret": "The reCAPTCHA secret key is invalid. Create a matching v2 checkbox secret for this app.",
        "missing-input-response": "Complete the reCAPTCHA challenge before continuing.",
        "invalid-input-response": "The reCAPTCHA response was invalid. Refresh the page and try again.",
        "bad-request": "The reCAPTCHA verification request was malformed.",
        "timeout-or-duplicate": "The reCAPTCHA challenge expired. Complete it again before continuing.",
    }
    message = "reCAPTCHA verification failed."
    if error_codes:
        message = " ".join(friendly_messages.get(code, code) for code in error_codes)
    return {
        "success": False,
        "message": message,
        "error_codes": error_codes,
    }


def _post_recaptcha(payload: dict) -> dict:
    encoded = parse.urlencode(payload).encode("utf-8")
    req = request.Request(RECAPTCHA_VERIFY_URL, data=encoded, method="POST")
    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))
