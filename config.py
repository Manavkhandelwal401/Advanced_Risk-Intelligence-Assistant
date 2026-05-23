"""
Central configuration helpers for ARIA.

The Streamlit app can run without optional AI/email credentials, but features
that call external services validate their required environment variables
before doing network work.
"""

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import dotenv_values, load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

    def dotenv_values(*args, **kwargs):
        return {}


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)


def _read_env_file(path: Path) -> dict[str, str]:
    try:
        values = dict(dotenv_values(path))
    except Exception:
        values = {}
    if values:
        return {key: str(value) for key, value in values.items() if value is not None}

    parsed: dict[str, str] = {}
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            parsed[key.strip()] = value
    except OSError:
        pass
    return parsed


_DOTENV_VALUES = _read_env_file(ENV_PATH)


MAX_UPLOAD_SIZE_MB = 200
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
RECAPTCHA_V2_TEST_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
RECAPTCHA_V2_TEST_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"


@dataclass(frozen=True)
class Settings:
    app_env: str
    db_path: str
    app_secret: str | None
    cloud_model_name: str
    groq_api_key: str | None
    email_sender: str | None
    email_password: str | None
    email_receiver: str | None
    email_dev_mode: bool
    smtp_server: str
    smtp_port: int
    recaptcha_site_key: str | None
    recaptcha_secret_key: str | None
    recaptcha_using_test_keys: bool


def _streamlit_secret(name: str) -> str | None:
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:
        return None
    if value is None:
        return None
    return str(value)


def _optional_setting(name: str) -> str | None:
    value = os.getenv(name)
    if value is not None and value.strip():
        return value.strip()

    value = _streamlit_secret(name)
    if value is not None and value.strip():
        return value.strip()

    value = _DOTENV_VALUES.get(name)
    if value is not None and str(value).strip():
        return str(value).strip()

    return None


def _looks_like_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().lower()
    return normalized in {
        "",
        "change-me",
        "changeme",
        "your-secret",
        "your-key",
        "your-api-key",
        "replace-me",
        "todo",
    }


def _setting(name: str, default: str) -> str:
    value = _optional_setting(name)
    return value if value is not None else default


def _bool_setting(name: str, default: bool = False) -> bool:
    value = _optional_setting(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    db_path_raw = _setting("ARIA_DB_PATH", str(BASE_DIR / "aria.db"))
    db_path_obj = Path(db_path_raw).expanduser()
    if not db_path_obj.is_absolute():
        db_path_obj = BASE_DIR / db_path_obj
    db_path = str(db_path_obj)
    smtp_port_raw = _setting("SMTP_PORT", "587")
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT must be a valid integer.") from exc

    app_env = _setting("APP_ENV", "development").strip() or "development"
    use_recaptcha_test_keys = _bool_setting(
        "RECAPTCHA_USE_TEST_KEYS",
        default=app_env.lower() in {"development", "testing", "test"},
    )
    email_dev_mode = _bool_setting(
        "EMAIL_DEV_MODE",
        default=app_env.lower() in {"development", "testing", "test"},
    )
    recaptcha_site_key = _optional_setting("RECAPTCHA_SITE_KEY")
    recaptcha_secret_key = _optional_setting("RECAPTCHA_SECRET_KEY")
    if use_recaptcha_test_keys and app_env.lower() != "production":
        recaptcha_site_key = RECAPTCHA_V2_TEST_SITE_KEY
        recaptcha_secret_key = RECAPTCHA_V2_TEST_SECRET_KEY

    return Settings(
        app_env=app_env,
        db_path=db_path,
        app_secret=_optional_setting("APP_SECRET"),
        cloud_model_name=_setting(
            "CLOUD_MODEL_NAME",
            "meta-llama/llama-4-scout-17b-16e-instruct",
        ).strip(),
        groq_api_key=_optional_setting("GROQ_API_KEY"),
        email_sender=_optional_setting("EMAIL_SENDER"),
        email_password=_optional_setting("EMAIL_PASSWORD"),
        email_receiver=_optional_setting("EMAIL_RECEIVER"),
        email_dev_mode=email_dev_mode and app_env.lower() != "production",
        smtp_server=_setting("SMTP_SERVER", "smtp.gmail.com").strip(),
        smtp_port=smtp_port,
        recaptcha_site_key=recaptcha_site_key,
        recaptcha_secret_key=recaptcha_secret_key,
        recaptcha_using_test_keys=use_recaptcha_test_keys and app_env.lower() != "production",
    )


def validate_startup_config() -> list[str]:
    """
    Validate non-optional startup configuration.

    Optional integrations such as Groq and SMTP are validated at the moment
    those features are used, so the dashboard can still run for local analysis.
    """
    settings = get_settings()
    warnings: list[str] = []

    db_parent = Path(settings.db_path).expanduser().resolve().parent
    if not db_parent.exists():
        raise RuntimeError(f"ARIA_DB_PATH parent directory does not exist: {db_parent}")

    if not settings.groq_api_key:
        warnings.append("GROQ_API_KEY is not set. AI advisory will be disabled until configured.")

    sender_fields = [settings.email_sender, settings.email_password]
    if any(sender_fields) and not all(sender_fields):
        warnings.append(
            "Report email settings are incomplete. Set EMAIL_SENDER and EMAIL_PASSWORD together."
        )
    if settings.email_receiver and not all(sender_fields):
        warnings.append("EMAIL_RECEIVER is set, but sender SMTP credentials are missing.")
    if not all(sender_fields) and settings.email_dev_mode:
        warnings.append(
            "EMAIL_DEV_MODE is active. OTP codes will be shown in the local UI instead of sent by SMTP."
        )
    if not settings.app_secret:
        warnings.append("APP_SECRET is not set. OTP verification will be disabled until configured.")
    elif len(settings.app_secret) < 32 or _looks_like_placeholder(settings.app_secret):
        raise RuntimeError("APP_SECRET must be a non-placeholder random value of at least 32 characters.")
    if not all([settings.recaptcha_site_key, settings.recaptcha_secret_key]):
        warnings.append(
            "Google reCAPTCHA is not fully configured. Registration will require "
            "RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY."
        )
    if settings.app_env.lower() == "production":
        if settings.email_dev_mode:
            raise RuntimeError("EMAIL_DEV_MODE must be false in production.")
        if settings.recaptcha_using_test_keys:
            raise RuntimeError("RECAPTCHA_USE_TEST_KEYS must be false in production.")
        if settings.recaptcha_site_key == RECAPTCHA_V2_TEST_SITE_KEY:
            raise RuntimeError("Google reCAPTCHA test site key cannot be used in production.")
        if settings.recaptcha_secret_key == RECAPTCHA_V2_TEST_SECRET_KEY:
            raise RuntimeError("Google reCAPTCHA test secret key cannot be used in production.")
    elif settings.recaptcha_using_test_keys:
        warnings.append(
            "Using local verification mode for development. "
            "Configure real Google reCAPTCHA v2 keys before production."
        )

    return warnings


def require_groq_config() -> Settings:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to .env before generating AI insights."
        )
    return settings


def require_email_config() -> Settings:
    settings = get_settings()
    if not all([settings.email_sender, settings.email_password, settings.email_receiver]):
        raise RuntimeError(
            "Email credentials missing. Set EMAIL_SENDER, EMAIL_PASSWORD, "
            "and EMAIL_RECEIVER in .env."
        )
    return settings


def require_smtp_sender_config() -> Settings:
    settings = get_settings()
    if not all([settings.email_sender, settings.email_password]):
        raise RuntimeError(
            "Email sender credentials missing. Set EMAIL_SENDER and EMAIL_PASSWORD in .env."
        )
    return settings


def require_app_secret() -> Settings:
    settings = get_settings()
    if not settings.app_secret:
        raise RuntimeError("APP_SECRET is missing. Add it before using OTP verification.")
    return settings


def require_recaptcha_config() -> Settings:
    settings = get_settings()
    if not all([settings.recaptcha_site_key, settings.recaptcha_secret_key]):
        raise RuntimeError(
            "Google reCAPTCHA credentials missing. Set RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY."
        )
    return settings
