"""Google reCAPTCHA Streamlit component wrapper."""

from pathlib import Path

import streamlit.components.v1 as components


_COMPONENT_PATH = Path(__file__).resolve().parent.parent / "components" / "recaptcha"
_recaptcha = components.declare_component("aria_recaptcha", path=str(_COMPONENT_PATH))


def recaptcha_widget(
    site_key: str,
    theme: str = "light",
    size: str = "normal",
    key: str = "aria_recaptcha",
) -> str | None:
    if not site_key:
        return None
    widget_size = "normal" if size == "normal" else "compact"
    return _recaptcha(site_key=site_key, theme=theme, size=widget_size, default=None, key=key)
