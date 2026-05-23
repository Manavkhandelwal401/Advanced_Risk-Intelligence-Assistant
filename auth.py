"""
Authentication helpers for ARIA.

Passwords are stored as secure hashes. bcrypt is used when installed; otherwise
ARIA falls back to PBKDF2-SHA256 from the Python standard library so the app can
still run in constrained demo environments. Legacy plaintext records can be
upgraded after a successful login.
"""

import hashlib
import hmac
import secrets

try:
    import bcrypt
except ImportError:
    bcrypt = None

from database.history_repository import (
    get_user_by_email,
    register_user,
    update_user_password_hash,
)


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    password_bytes = password.encode("utf-8")
    if bcrypt is not None:
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")

    iterations = 260000
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password_bytes,
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored_password: str) -> tuple[bool, bool]:
    """
    Returns (is_valid, needs_rehash).

    `needs_rehash` is True only for legacy plaintext passwords.
    """
    if not password or not stored_password:
        return False, False

    if stored_password.startswith("$2a$") or stored_password.startswith("$2b$"):
        if bcrypt is None:
            return False, False
        is_valid = bcrypt.checkpw(
            password.encode("utf-8"),
            stored_password.encode("utf-8"),
        )
        return is_valid, False

    if stored_password.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, stored_digest = stored_password.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()
        except (TypeError, ValueError):
            return False, False
        return hmac.compare_digest(digest, stored_digest), False

    # Legacy compatibility for databases created before hashing existed.
    return password == stored_password, password == stored_password


def register_user_account(name, email, password, business_type, starting_cash=100000.0):
    password_hash = hash_password(password)
    return register_user_account_with_hash(
        name,
        email,
        password_hash,
        business_type,
        starting_cash,
    )


def register_user_account_with_hash(
    name,
    email,
    password_hash,
    business_type,
    starting_cash=100000.0,
):
    return register_user(
        name,
        email,
        password_hash,
        business_type,
        starting_cash,
        email_verified=True,
    )


def authenticate_user(email: str, password: str):
    normalized_email = str(email or "").strip().lower()
    if not normalized_email or not password:
        return None

    user = get_user_by_email(normalized_email)
    if not user:
        return None

    is_valid, needs_rehash = verify_password(password, user["password"])
    if not is_valid:
        return None

    if not bool(user["email_verified"]):
        return None

    if needs_rehash:
        update_user_password_hash(user["user_id"], hash_password(password))

    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
        "business_type": user["business_type"],
        "starting_cash": user["starting_cash"],
        "email_verified": bool(user["email_verified"]),
        "wallpaper_theme": user["wallpaper_theme"],
    }


def reset_user_password(email: str, new_password: str) -> bool:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        raise ValueError("Enter the account email address.")

    user = get_user_by_email(normalized_email)
    if not user or not bool(user["email_verified"]):
        return False

    update_user_password_hash(user["user_id"], hash_password(new_password))
    return True
