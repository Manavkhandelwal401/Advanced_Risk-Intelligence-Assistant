"""
app.py  –  ARIA User Interface Module
ARIA – Advanced Risk Intelligence Assistant
Streamlit-based interactive dashboard.

Run:
    streamlit run app.py

Modules implemented (Chapter 4.3):
  1. User Interface Module   – dashboard, upload, visualization
  2. Data Processing Module  – CSV validation & storage
  3. Risk Assessment Module  – live risk metrics & 30-day projection
  4. AI Recommendation Module– on-demand LLM insights
  5. Database Module         – SQLite read/write via repository layer
"""

import sys
import os
import json
from html import escape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import pandas as pd
from pandas.errors import EmptyDataError
import plotly.graph_objects as go
import streamlit as st

# ── Path fix (run from ARIA/ folder) ────────────────────────────────────
sys.path.insert(0, BASE_DIR)

from config import MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_MB, get_settings, validate_startup_config
from auth import authenticate_user, hash_password, register_user_account_with_hash, reset_user_password

from database.history_repository import (
    get_existing_financial_dates,
    get_risk_history,
    get_risk_reports,
    get_ai_recommendations_for_user,
    get_user_by_email,
    get_user_by_id,
    update_user_wallpaper,
    get_platform_average_risk,
    save_financial_records,
    delete_financial_data,
    save_risk_report,
    update_risk_report_email_status,
    save_ai_recommendation,
    consume_email_verification_code,
)
from workflows.financial_engine import (
    generate_financial_summary,
    project_30_day_risk,
    simulate_scenario
)
from models.orchestrator import generate_ai
from notifications.email_service import send_otp_email, send_report_email
from setup_db import create_tables
from ui.recaptcha import recaptcha_widget
from ui.theme import apply_runtime_theme_overrides
from verification import create_email_verification, verify_email_otp, verify_recaptcha_token


# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(
    page_title="ARIA – Advanced Risk Intelligence Assistant",
    page_icon="📊",
    layout="wide"
)

try:
    _config_warnings = validate_startup_config()
    runtime_settings = get_settings()
except RuntimeError as config_error:
    import streamlit as st
    st.error(f"Startup configuration error: {config_error}")
    st.stop()

# Session Restoration from Query Parameters (Moved to top)
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if st.session_state.auth_user is None:
    try:
        qp_user_id = st.query_params.get("user_id")
        qp_token = st.query_params.get("token")
        if isinstance(qp_user_id, list):
            qp_user_id = qp_user_id[0]
        if isinstance(qp_token, list):
            qp_token = qp_token[0]
            
        if qp_user_id and qp_token and runtime_settings.app_secret:
            import hmac
            import hashlib
            expected = hmac.new(
                runtime_settings.app_secret.encode("utf-8"),
                str(qp_user_id).encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(expected, qp_token):
                user_row = get_user_by_id(int(qp_user_id))
                if user_row:
                    st.session_state.auth_user = {
                        "user_id": user_row["user_id"],
                        "name": user_row["name"],
                        "email": user_row["email"],
                        "business_type": user_row["business_type"],
                        "starting_cash": user_row["starting_cash"],
                        "email_verified": bool(user_row["email_verified"]),
                        "wallpaper_theme": user_row["wallpaper_theme"],
                    }
                    st.session_state.wallpaper_theme = user_row["wallpaper_theme"]
    except Exception:
        pass

# Determine and Restore Wallpaper Theme
if "wallpaper_theme" not in st.session_state:
    st.session_state.wallpaper_theme = st.query_params.get("wallpaper", "None")

if st.session_state.get("auth_user"):
    st.session_state.wallpaper_theme = st.session_state.auth_user.get("wallpaper_theme", "None")


def _current_theme_type():
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:
        return "dark" if st.get_option("theme.base") == "dark" else "light"


def active_theme_type():
    wp = st.session_state.get("wallpaper_theme", "None")
    if wp in ["Cosmic Nebula", "Midnight Stars", "Cyber Grid"]:
        return "dark"
    elif wp in ["Morning Sky", "Minimal Starlet", "Architect Grid"]:
        return "light"
    return _current_theme_type()


def is_dark_theme():
    return active_theme_type() == "dark"


def inject_wallpaper_css(theme_name):
    css_rules = ""
    if theme_name == "Cosmic Nebula":
        css_rules = """
        [data-testid="stAppViewContainer"] {
          background: radial-gradient(circle at 20% 30%, rgba(88, 28, 135, 0.15) 0%, transparent 50%), 
                      radial-gradient(circle at 80% 70%, rgba(29, 78, 216, 0.12) 0%, transparent 50%), 
                      #0f141a !important;
        }
        """
    elif theme_name == "Midnight Stars":
        css_rules = """
        [data-testid="stAppViewContainer"] {
          background-color: #0b0f19 !important;
          background-image: radial-gradient(circle at 50% 50%, rgba(255,255,255,0.06) 1px, transparent 1px), 
                            radial-gradient(circle at 20% 80%, rgba(255,255,255,0.04) 1.5px, transparent 1.5px) !important;
          background-size: 80px 80px, 120px 120px !important;
        }
        """
    elif theme_name == "Cyber Grid":
        css_rules = """
        [data-testid="stAppViewContainer"] {
          background-color: #0d1117 !important;
          background-image: linear-gradient(to right, rgba(56, 189, 248, 0.03) 1px, transparent 1px), 
                            linear-gradient(to bottom, rgba(56, 189, 248, 0.03) 1px, transparent 1px) !important;
          background-size: 32px 32px !important;
        }
        """
    elif theme_name == "Morning Sky":
        css_rules = """
        [data-testid="stAppViewContainer"] {
          background: linear-gradient(135deg, #f0f7ff 0%, #faf5ff 50%, #fff7ed 100%) !important;
        }
        """
    elif theme_name == "Minimal Starlet":
        css_rules = """
        [data-testid="stAppViewContainer"] {
          background-color: #f8fafc !important;
          background-image: radial-gradient(#cbd5e1 1.2px, transparent 1.2px) !important;
          background-size: 40px 40px !important;
        }
        """
    elif theme_name == "Architect Grid":
        css_rules = """
        [data-testid="stAppViewContainer"] {
          background-color: #f8fafc !important;
          background-image: radial-gradient(circle, rgba(148, 163, 184, 0.15) 1.5px, transparent 1.5px) !important;
          background-size: 20px 20px !important;
        }
        """
    if css_rules:
        st.markdown(f"<style>{css_rules}</style>", unsafe_allow_html=True)


inject_wallpaper_css(st.session_state.wallpaper_theme)

# Render Global Styling and Client-Side Persistence
is_logged_in_js = "true" if st.session_state.get("auth_user") is not None else "false"

st.markdown(f"""<img src="x" onerror="(function(){{try{{let targetWindow=window;try{{if(window.parent&&window.parent.location.search!==undefined){{targetWindow=window.parent;}}}}catch(e){{}}const urlParams=new URLSearchParams(targetWindow.location.search);const qpUserId=urlParams.get('user_id');const qpToken=urlParams.get('token');const qpWp=urlParams.get('wallpaper');if(qpWp){{localStorage.setItem('aria_wallpaper_theme',qpWp);}}const storedWp=localStorage.getItem('aria_wallpaper_theme')||'None';let needsReload=false;const isLoggedIn={is_logged_in_js};if(!isLoggedIn){{if(storedWp!=='None'&&qpWp!==storedWp){{urlParams.set('wallpaper',storedWp);needsReload=true;}}}}if(qpUserId&&qpToken){{localStorage.setItem('aria_user_id',qpUserId);localStorage.setItem('aria_token',qpToken);}}else{{const storedUserId=localStorage.getItem('aria_user_id');const storedToken=localStorage.getItem('aria_token');if(storedUserId&&storedToken){{if(!isLoggedIn){{if(qpUserId===storedUserId&&qpToken===storedToken){{localStorage.removeItem('aria_user_id');localStorage.removeItem('aria_token');}}else{{urlParams.set('user_id',storedUserId);urlParams.set('token',storedToken);needsReload=true;}}}}}}}}if(needsReload){{targetWindow.location.search=urlParams.toString();}}}}catch(err){{console.error('Session persistence error:',err);}}}})()\" style=\"display:none;\"/>""", unsafe_allow_html=True)

is_dark = is_dark_theme()
bg = "#0f141a" if is_dark else "#f7f8fa"
panel = "#151b23" if is_dark else "#ffffff"
panel_soft = "#1d2430" if is_dark else "#f3f5f7"
text = "#edf2f7" if is_dark else "#17202a"
muted = "#b9c2cf" if is_dark else "#667085"
subtle = "#8d99a8" if is_dark else "#98a2b3"
border = "#303846" if is_dark else "#cbd5e1"
border_strong = "#465164" if is_dark else "#94a3b8"
accent = "#9aa4b2" if is_dark else "#475467"
accent_soft = "#202735" if is_dark else "#f2f4f7"
good = "#8fb9a0" if is_dark else "#4f7b63"
warn = "#d19791" if is_dark else "#8f4b46"
risk = "#d19791" if is_dark else "#8f4b46"
neutral = "#a8b3c1" if is_dark else "#64748b"
chart_good = "#8fb9a0" if is_dark else "#4f7b63"
chart_risk = "#d19791" if is_dark else "#8f4b46"
chart_neutral = "#a8b3c1" if is_dark else "#64748b"

st.markdown(f"""
<style>
:root {{
  --aria-bg: {bg};
  --aria-panel: {panel};
  --aria-panel-soft: {panel_soft};
  --aria-text: {text};
  --aria-muted: {muted};
  --aria-subtle: {subtle};
  --aria-border: {border};
  --aria-border-strong: {border_strong};
  --aria-accent: {accent};
  --aria-accent-soft: {accent_soft};
  --aria-good: {good};
  --aria-warn: {warn};
  --aria-risk: {risk};
  --aria-neutral: {neutral};
  --aria-chart-good: {chart_good};
  --aria-chart-risk: {chart_risk};
  --aria-chart-neutral: {chart_neutral};
  --aria-shadow: none;
}}

#GithubIcon, 
header a[href*="github.com"], 
header a[href*="fork"], 
header a[href*="streamlit"] {{
  display: none !important;
}}

footer {{
  display: none !important;
}}

header[data-testid="stHeader"] {{
  background-color: transparent !important;
}}

button[data-testid="collapsedSidebarCollapsed"],
button[data-testid="collapsedSidebarCollapsed"] * {{
  color: var(--aria-text) !important;
}}

html, body, [class*="css"] {{
  font-family: Inter, "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
}}

.stApp,
[data-testid="stAppViewContainer"] {{
  background: var(--aria-bg);
  color: var(--aria-text);
}}

.main .block-container {{
  padding-top: 1rem;
  padding-bottom: 2.2rem;
  max-width: min(1440px, calc(100vw - 3rem));
}}

h1, h2, h3, h4, h5, h6,
p, li, label, span, div[data-testid="stMarkdownContainer"] {{
  color: var(--aria-text);
  letter-spacing: 0;
}}

h1 {{ font-size: 2.0rem; font-weight: 800; }}
h2 {{ font-size: 1.45rem; font-weight: 700; }}
h3 {{ font-size: 1.15rem; font-weight: 650; }}
h4 {{ font-size: 0.95rem; font-weight: 600; }}

.aria-hero {{
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--aria-border);
  border-radius: 0;
  padding: 8px 0 18px;
  margin-bottom: 18px;
  color: var(--aria-text);
}}

.aria-hero h1 {{
  color: var(--aria-text);
  font-size: 2.0rem;
  line-height: 1.15;
  margin: 0 0 5px 0;
  font-weight: 800;
}}

.aria-hero p {{
  color: var(--aria-muted);
  font-size: 0.95rem;
  max-width: 760px;
  margin: 0;
}}

.aria-section-kicker {{
  color: var(--aria-muted);
  text-transform: uppercase;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  margin-bottom: 4px;
}}

.aria-section-title {{
  font-size: 1.45rem;
  font-weight: 700;
  margin: 0;
  color: var(--aria-text);
}}

.aria-section-subtitle {{
  color: var(--aria-muted);
  margin-top: 4px;
  margin-bottom: 12px;
  font-size: 0.95rem;
}}

.aria-card {{
  background: var(--aria-panel);
  border: 1px solid var(--aria-border);
  border-radius: 8px;
  padding: 14px;
  min-height: 112px;
  box-shadow: var(--aria-shadow);
  height: 100%;
}}

.aria-kpi-grid {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}}

.aria-kpi-grid-secondary {{
  grid-template-columns: repeat(3, minmax(0, 1fr));
}}

.aria-card-label {{
  color: var(--aria-muted);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  margin-bottom: 8px;
}}

.aria-card-value {{
  color: var(--aria-text);
  font-size: 1.45rem;
  font-weight: 800;
  line-height: 1.22;
  overflow-wrap: anywhere;
}}

.aria-card-help {{
  color: var(--aria-muted);
  font-size: 0.78rem;
  margin-top: 8px;
}}

.aria-card-positive,
.aria-card-danger,
.aria-card-warning,
.aria-card-neutral {{
  border-left: 2px solid var(--aria-border-strong);
}}

.aria-card-positive {{ border-left-color: var(--aria-chart-good); }}
.aria-card-danger {{ border-left-color: var(--aria-chart-risk); }}
.aria-card-warning {{ border-left-color: var(--aria-chart-risk); }}

.aria-exec-panel {{
  background: var(--aria-panel);
  border: 1px solid var(--aria-border);
  border-radius: 8px;
  padding: 14px;
  margin: 8px 0 12px;
  box-shadow: var(--aria-shadow);
}}

.aria-exec-panel h4 {{
  margin: 0 0 8px 0;
  font-size: 1rem;
}}

.aria-exec-panel p {{
  color: var(--aria-muted);
  margin: 0 0 8px 0;
}}

.aria-risk-panel {{
  background: var(--aria-panel);
  border: 1px solid var(--aria-border);
  border-radius: 8px;
  padding: 15px;
  box-shadow: var(--aria-shadow);
}}

.aria-risk-badge {{
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 9px;
  font-weight: 700;
  font-size: 0.8rem;
  border: 1px solid transparent;
}}

.aria-risk-low {{
  background: color-mix(in srgb, var(--aria-good) 8%, transparent);
  color: var(--aria-good);
  border-color: color-mix(in srgb, var(--aria-good) 28%, var(--aria-border));
}}

.aria-risk-moderate {{
  background: color-mix(in srgb, var(--aria-warn) 9%, transparent);
  color: var(--aria-warn);
  border-color: color-mix(in srgb, var(--aria-warn) 30%, var(--aria-border));
}}

.aria-risk-high {{
  background: color-mix(in srgb, var(--aria-risk) 9%, transparent);
  color: var(--aria-risk);
  border-color: color-mix(in srgb, var(--aria-risk) 30%, var(--aria-border));
}}

.aria-progress {{
  width: 100%;
  height: 8px;
  background: var(--aria-panel-soft);
  border-radius: 999px;
  overflow: hidden;
  margin-top: 12px;
}}

.aria-progress-fill {{
  height: 8px;
  border-radius: 999px;
}}

.aria-note {{
  background: transparent;
  border: 1px solid var(--aria-border);
  color: var(--aria-muted);
  border-radius: 8px;
  padding: 9px 11px;
  margin-bottom: 10px;
  font-size: 0.86rem;
}}

.aria-status {{
  background: transparent;
  border: 1px solid var(--aria-border);
  border-left: 2px solid var(--aria-neutral);
  border-radius: 8px;
  padding: 8px 10px;
  margin: 8px 0;
  color: var(--aria-text);
  font-size: 0.86rem;
  line-height: 1.45;
}}

.aria-status-info {{ border-left-color: var(--aria-chart-neutral); }}
.aria-status-success {{ border-left-color: var(--aria-chart-good); }}
.aria-status-warning {{ border-left-color: var(--aria-chart-risk); }}
.aria-status-error,
.aria-status-danger {{ border-left-color: var(--aria-chart-risk); }}

.aria-history-summary {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 10px 0 14px;
}}

.aria-history-summary .aria-card {{
  min-height: 92px;
}}

.aria-empty {{
  background: var(--aria-panel-soft);
  border: 1px dashed var(--aria-border-strong);
  border-radius: 8px;
  color: var(--aria-muted);
  padding: 13px;
  font-size: 0.88rem;
}}

div[data-testid="stMetric"] {{
  background: var(--aria-panel);
  border: 1px solid var(--aria-border);
  border-radius: 8px;
  padding: 14px 16px;
  box-shadow: none;
}}

section[data-testid="stSidebar"] {{
  background: var(--aria-panel);
  border-right: 1px solid var(--aria-border);
}}

section[data-testid="stSidebar"],
section[data-testid="stSidebar"] * {{
  color: var(--aria-text);
}}

section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
  font-size: 1.02rem;
}}

section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li {{
  color: var(--aria-muted);
  font-size: 0.86rem;
}}

div[data-testid="stAlert"] {{
  background: transparent;
  border: 1px solid var(--aria-border);
  border-left: 2px solid var(--aria-neutral);
  border-radius: 8px;
  color: var(--aria-text);
  min-height: auto;
}}

div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {{
  font-size: 0.86rem;
  line-height: 1.45;
}}

.stButton > button,
.stDownloadButton > button {{
  border-radius: 7px;
  border: 1px solid var(--aria-border-strong);
  background: var(--aria-panel);
  color: var(--aria-text);
  font-weight: 650;
  min-height: 2.45rem;
  white-space: normal;
}}

.stButton > button:hover,
.stDownloadButton > button:hover,
.stButton > button:focus,
.stDownloadButton > button:focus {{
  border-color: var(--aria-accent);
  color: var(--aria-text);
  background: var(--aria-panel-soft);
}}

.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stFileUploader {{
  border-radius: 7px;
  color: var(--aria-text);
  background: var(--aria-panel);
  border: 1px solid var(--aria-border) !important;
}}

.stTabs [data-baseweb="tab-list"] {{
  gap: 6px;
  border-bottom: 1px solid var(--aria-border);
}}

.stTabs [data-baseweb="tab"] {{
  border-radius: 7px 7px 0 0;
  padding: 9px 13px;
  background: transparent;
  color: var(--aria-muted);
}}

.stTabs [aria-selected="true"] {{
  background: var(--aria-panel-soft);
  color: var(--aria-text);
}}

div[data-testid="stDataFrame"] {{
  border: none !important;
  border-radius: 8px;
  overflow: hidden;
}}

hr {{
  margin: 1rem 0;
  border-color: var(--aria-border);
  opacity: 0.45;
}}

.aria-section-spacer {{
  height: 18px;
}}

/* Custom overrides for selectbox, number buttons, eye icon, recaptcha, and charts */
div[data-baseweb="select"] > div,
div[data-baseweb="select"] *,
div[role="listbox"] * {{
  background-color: var(--aria-panel) !important;
  color: var(--aria-text) !important;
}}
div[data-testid="stTextInputPasswordVisibility"] button,
div[data-testid="stTextInputPasswordVisibility"] *,
.stTextInput button,
.stTextInput button *,
.stNumberInput button {{
  background-color: transparent !important;
  color: var(--aria-text) !important;
  border: none !important;
}}
.stNumberInput button:hover {{
  background-color: var(--aria-panel-soft) !important;
}}
div[data-testid="stPlotlyChart"] {{
  background: var(--aria-panel) !important;
  border: 1px solid var(--aria-border) !important;
  border-radius: 8px !important;
  padding: 12px !important;
  box-shadow: var(--aria-shadow) !important;
}}
div[data-testid="stDataFrame"] {{
  background: var(--aria-panel) !important;
  border: none !important;
}}

@media (max-width: 760px) {{
  .main .block-container {{
    padding-left: 1rem;
    padding-right: 1rem;
    max-width: 100%;
  }}

  .aria-hero {{
    padding: 18px;
  }}

  .aria-hero h1 {{
    font-size: 1.45rem;
  }}

  .aria-card {{
    min-height: auto;
    padding: 14px;
  }}

  .aria-kpi-grid,
  .aria-kpi-grid-secondary {{
    grid-template-columns: 1fr;
  }}

  .aria-card-value {{
    font-size: 1.12rem;
    overflow-wrap: anywhere;
  }}

  .stTabs [data-baseweb="tab-list"] {{
    overflow-x: auto;
  }}
}}

@media (min-width: 1600px) {{
  .main .block-container {{
    max-width: 1480px;
  }}
}}

@media (min-width: 761px) and (max-width: 1100px) {{
  .aria-kpi-grid,
  .aria-kpi-grid-secondary {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}
}}
</style>

<div class="aria-hero">
  <h1>ARIA - Advanced Risk Intelligence Assistant</h1>
  <p>Business Risk Intelligence</p>
</div>""",
unsafe_allow_html=True
)

apply_runtime_theme_overrides(st)

# ── Auto-create tables if DB doesn't exist yet ───────────────────────────
try:
    create_tables(verbose=False)
except Exception as db_error:
    st.error(f"Database startup error: {db_error}")
    st.stop()





def _request_ip_address():
    try:
        return st.context.ip_address
    except Exception:
        return None


def _clear_pending_registration():
    st.session_state.pending_registration = None
    st.session_state.registration_otp_sent = False


def _clear_pending_password_reset():
    st.session_state.pending_password_reset = None


def _smtp_sender_configured():
    return bool(runtime_settings.email_sender and runtime_settings.email_password)


def _otp_delivery_available():
    return _smtp_sender_configured() or runtime_settings.email_dev_mode


def _render_local_verification(key: str) -> str | None:
    st.caption("Local verification is enabled for localhost testing.")
    return "local-dev-captcha-ok"


def _render_verification_widget(key: str) -> str | None:
    if runtime_settings.recaptcha_using_test_keys:
        return _render_local_verification(key)
    return recaptcha_widget(
        runtime_settings.recaptcha_site_key or "",
        theme=active_theme_type(),
        key=key,
    )


def _deliver_otp_or_prepare_local(verification: dict, purpose_label: str) -> dict:
    if _smtp_sender_configured():
        send_otp_email(verification["email"], verification["otp_code"])
        return {"mode": "email", "message": f"{purpose_label} OTP sent to your email."}
    if runtime_settings.email_dev_mode:
        return {
            "mode": "local",
            "message": f"{purpose_label} OTP generated for local testing.",
            "otp_code": verification["otp_code"],
        }
    raise RuntimeError("SMTP email is not configured. Set EMAIL_SENDER and EMAIL_PASSWORD, or enable EMAIL_DEV_MODE for localhost.")


# ==============================
# SIDEBAR – Authentication / Registration
# ==============================
st.sidebar.header("Business Access")
st.sidebar.markdown(
    """
    **Workspace**

    Upload data, review risk, and export reports.

    **Quick Navigation**

    [Upload](#upload-financial-data) · [Dashboard](#financial-overview) · [Risk](#risk-assessment) · [Advisory](#ai-financial-advisory) · [History](#reports-and-recommendations) · [Simulation](#what-if-financial-simulation)
    """
)


if "pending_registration" not in st.session_state:
    st.session_state.pending_registration = None
if "registration_otp_sent" not in st.session_state:
    st.session_state.registration_otp_sent = False
if "pending_password_reset" not in st.session_state:
    st.session_state.pending_password_reset = None

if st.session_state.auth_user:
    current_user = st.session_state.auth_user
    st.sidebar.markdown(f"**Signed in:** {current_user['name']}")
    st.sidebar.caption(f"{current_user['email']} | {current_user['business_type']}")
    if st.sidebar.button("Log out"):
        st.session_state.auth_user = None
        st.query_params.clear()
        # Inject JS to clear localStorage on logout
        st.markdown(
"""<img src="x" onerror="
localStorage.removeItem('aria_user_id');
localStorage.removeItem('aria_token');
" style="display:none;"/>""",
            unsafe_allow_html=True
        )
        st.cache_data.clear()
        st.rerun()
else:
    tab_login, tab_register = st.sidebar.tabs(["Login", "Register"])

    with tab_login:
        st.subheader("Login")
        st.caption("Access your business dashboard securely.")
        login_email = st.text_input("Email", key="login_email")
        login_password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login"):
            user = authenticate_user(login_email, login_password)
            if user:
                st.session_state.auth_user = user
                st.session_state.wallpaper_theme = user.get("wallpaper_theme", "None")
                if runtime_settings.app_secret:
                    import hmac
                    import hashlib
                    token = hmac.new(
                        runtime_settings.app_secret.encode("utf-8"),
                        str(user["user_id"]).encode("utf-8"),
                        hashlib.sha256
                    ).hexdigest()
                    st.query_params["user_id"] = str(user["user_id"])
                    st.query_params["token"] = token
                    st.query_params["wallpaper"] = user.get("wallpaper_theme", "None")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Invalid email or password.")

        with st.expander("Forgot password"):
            st.caption("Reset access with a one-time code sent to your verified email.")
            reset_email = st.text_input("Account email", key="reset_email")
            reset_new_password = st.text_input("New password", type="password", key="reset_new_password")
            reset_ready = all([
                runtime_settings.app_secret,
                _otp_delivery_available(),
                runtime_settings.recaptcha_site_key,
                runtime_settings.recaptcha_secret_key,
            ])
            if not reset_ready:
                st.warning("Password reset needs APP_SECRET, verification config, and either SMTP credentials or EMAIL_DEV_MODE=true.")

            reset_recaptcha_token = _render_verification_widget("password_reset_verification")

            if st.button("Send Password Reset OTP", disabled=not reset_ready):
                try:
                    normalized_reset_email = reset_email.strip().lower()
                    reset_user = get_user_by_email(normalized_reset_email)
                    if not reset_user or not bool(reset_user["email_verified"]):
                        st.error("No verified account was found for that email.")
                    else:
                        recaptcha_result = verify_recaptcha_token(
                            reset_recaptcha_token,
                            remoteip=_request_ip_address(),
                        )
                        if not recaptcha_result.get("success"):
                            st.error(recaptcha_result.get("message", "reCAPTCHA verification failed."))
                        else:
                            verification = create_email_verification(
                                normalized_reset_email,
                                purpose="password_reset",
                            )
                            try:
                                delivery = _deliver_otp_or_prepare_local(verification, "Password reset")
                            except Exception:
                                consume_email_verification_code(verification["code_id"])
                                raise
                            st.session_state.pending_password_reset = {
                                "email": normalized_reset_email,
                                "expires_at": verification["expires_at"],
                                "delivery": delivery,
                            }
                            st.success(delivery["message"])
                except ValueError as validation_error:
                    st.error(str(validation_error))
                except Exception as reset_error:
                    st.error(f"Password reset failed: {reset_error}")

            pending_password_reset = st.session_state.pending_password_reset
            if pending_password_reset:
                delivery = pending_password_reset.get("delivery", {})
                st.info(
                    "OTP ready for "
                    f"{pending_password_reset['email']}. It expires at {pending_password_reset['expires_at']} UTC."
                )
                if delivery.get("mode") == "local":
                    st.code(delivery.get("otp_code", ""), language=None)
                reset_otp = st.text_input("Password Reset OTP", max_chars=6, key="password_reset_otp")
                reset_col, cancel_reset_col = st.columns(2)
                with reset_col:
                    if st.button("Verify OTP and Update Password"):
                        if not reset_new_password or len(reset_new_password) < 8:
                            st.error("Password must be at least 8 characters long.")
                        else:
                            otp_result = verify_email_otp(
                                pending_password_reset["email"],
                                reset_otp,
                                purpose="password_reset",
                            )
                            if not otp_result.get("success"):
                                st.error(otp_result.get("message", "OTP verification failed."))
                            else:
                                try:
                                    updated = reset_user_password(
                                        pending_password_reset["email"],
                                        reset_new_password,
                                    )
                                except ValueError as password_error:
                                    st.error(str(password_error))
                                    updated = False
                                if updated:
                                    _clear_pending_password_reset()
                                    st.success("Password updated. Log in with the new password.")
                                    st.rerun()
                                else:
                                    st.error("Could not update that account. Request a new code and try again.")
                with cancel_reset_col:
                    if st.button("Cancel Reset"):
                        _clear_pending_password_reset()
                        st.rerun()

    with tab_register:
        st.subheader("Register New Business")
        st.caption("Verify email ownership before the business profile is created.")
        reg_name = st.text_input("Business Name", key="reg_name")
        reg_email = st.text_input("Email", key="reg_email")
        reg_password = st.text_input("Password", type="password", key="reg_password")
        reg_btype = st.selectbox(
            "Business Type",
            ["Manufacturing", "Trading", "Wholesale", "Startup", "Service", "Other"],
            key="reg_btype",
        )
        reg_cash = st.number_input(
            "Starting Cash (₹)",
            min_value=0.0,
            value=100000.0,
            step=1000.0,
            key="reg_cash",
        )

        registration_security_ready = all([
            runtime_settings.app_secret,
            _otp_delivery_available(),
            runtime_settings.recaptcha_site_key,
            runtime_settings.recaptcha_secret_key,
        ])
        if not registration_security_ready:
            st.warning("Registration needs APP_SECRET, verification config, and either SMTP credentials or EMAIL_DEV_MODE=true.")
        elif runtime_settings.recaptcha_using_test_keys:
            st.caption("Local verification mode is active. Production should use Google reCAPTCHA v2.")

        recaptcha_token = _render_verification_widget("registration_verification")

        if st.button("Send Verification OTP", disabled=not registration_security_ready):
            if not all([reg_name.strip(), reg_email.strip(), reg_password]):
                st.error("Please fill all fields.")
            else:
                try:
                    normalized_email = reg_email.strip().lower()
                    if get_user_by_email(normalized_email):
                        st.error("Email already registered. Try logging in.")
                    else:
                        recaptcha_result = verify_recaptcha_token(
                            recaptcha_token,
                            remoteip=_request_ip_address(),
                        )
                        if not recaptcha_result.get("success"):
                            st.error(recaptcha_result.get("message", "reCAPTCHA verification failed."))
                        else:
                            password_hash = hash_password(reg_password)
                            verification = create_email_verification(normalized_email)
                            try:
                                delivery = _deliver_otp_or_prepare_local(verification, "Verification")
                            except Exception:
                                consume_email_verification_code(verification["code_id"])
                                raise
                            st.session_state.pending_registration = {
                                "name": reg_name.strip(),
                                "email": normalized_email,
                                "password_hash": password_hash,
                                "business_type": reg_btype,
                                "starting_cash": reg_cash,
                                "expires_at": verification["expires_at"],
                                "delivery": delivery,
                            }
                            st.session_state.registration_otp_sent = True
                            st.success(delivery["message"])
                except ValueError as validation_error:
                    st.error(str(validation_error))
                except Exception as registration_error:
                    st.error(f"Registration failed: {registration_error}")

        pending_registration = st.session_state.pending_registration
        if pending_registration:
            delivery = pending_registration.get("delivery", {})
            st.info(
                "OTP ready for "
                f"{pending_registration['email']}. It expires at {pending_registration['expires_at']} UTC."
            )
            if delivery.get("mode") == "local":
                st.code(delivery.get("otp_code", ""), language=None)
            otp_input = st.text_input("Email OTP", max_chars=6, key="registration_otp")
            verify_col, cancel_col = st.columns(2)
            with verify_col:
                if st.button("Verify OTP and Create Account"):
                    otp_result = verify_email_otp(
                        pending_registration["email"],
                        otp_input,
                    )
                    if not otp_result.get("success"):
                        st.error(otp_result.get("message", "OTP verification failed."))
                    else:
                        try:
                            new_id = register_user_account_with_hash(
                                pending_registration["name"],
                                pending_registration["email"],
                                pending_registration["password_hash"],
                                pending_registration["business_type"],
                                pending_registration["starting_cash"],
                            )
                        except Exception as registration_error:
                            st.error(f"Registration failed: {registration_error}")
                            new_id = None
                        if new_id:
                            st.session_state.auth_user = {
                                "user_id": new_id,
                                "name": pending_registration["name"],
                                "email": pending_registration["email"],
                                "business_type": pending_registration["business_type"],
                                "starting_cash": pending_registration["starting_cash"],
                                "email_verified": True,
                                "wallpaper_theme": "None",
                            }
                            st.session_state.wallpaper_theme = "None"
                            if runtime_settings.app_secret:
                                import hmac
                                import hashlib
                                token = hmac.new(
                                    runtime_settings.app_secret.encode("utf-8"),
                                    str(new_id).encode("utf-8"),
                                    hashlib.sha256
                                ).hexdigest()
                                st.query_params["user_id"] = str(new_id)
                                st.query_params["token"] = token
                                st.query_params["wallpaper"] = "None"
                            _clear_pending_registration()
                            st.success("Business registered and email verified.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Email already registered. Try logging in.")
            with cancel_col:
                if st.button("Cancel Verification"):
                    _clear_pending_registration()
# Render Wallpaper UI Selector (visible to all users, logged-in or logged-out)
st.sidebar.markdown("---")
st.sidebar.subheader("UI Customization")
is_dark = _current_theme_type() == "dark"
if is_dark:
    wallpapers = ["None", "Cosmic Nebula", "Midnight Stars", "Cyber Grid"]
else:
    wallpapers = ["None", "Morning Sky", "Minimal Starlet", "Architect Grid"]
    
current_wp = st.session_state.get("wallpaper_theme", "None")
if current_wp not in wallpapers:
    current_wp = "None"
    
selected_wp = st.sidebar.selectbox("Wallpaper Theme", wallpapers, index=wallpapers.index(current_wp))
if selected_wp != current_wp:
    st.session_state.wallpaper_theme = selected_wp
    if st.session_state.get("auth_user"):
        user_id = st.session_state.auth_user["user_id"]
        update_user_wallpaper(user_id, selected_wp)
        st.session_state.auth_user["wallpaper_theme"] = selected_wp
    st.query_params["wallpaper"] = selected_wp
    st.rerun()

if not st.session_state.auth_user:
    st.info("Log in or register a business to access the dashboard.")
    st.stop()
    raise SystemExit

user_id = st.session_state.auth_user["user_id"]

if "latest_recommendation" not in st.session_state:
    st.session_state.latest_recommendation = None


REQUIRED_UPLOAD_COLUMNS = {"date", "revenue", "expenses"}
CSV_CHUNK_ROWS = 50000
GENERIC_METADATA_COLUMNS = {
    "channel", "category", "product", "service", "region", "location",
    "customer", "client", "segment", "notes", "description", "invoice_id",
    "payment_status", "department", "team", "unit", "units", "quantity",
}
DOMAIN_METADATA_COLUMNS = {
    "manufacturing": {"inventory", "raw_material", "production_volume", "units_produced", "defects", "capacity_utilization"},
    "trading": {"supplier", "stock", "inventory", "purchase_cost", "units_sold", "margin_band"},
    "wholesale": {"supplier", "stock", "warehouse", "bulk_units", "units_sold", "margin_band"},
    "startup": {"mrr", "arr", "active_users", "churn", "cac", "ltv", "runway_note", "funding_stage"},
    "service": {"project", "billable_hours", "utilization", "retainer", "client_type"},
    "other": set(),
}


def normalize_upload_column(column_name):
    return str(column_name).strip().lower().replace(" ", "_")


def relevant_metadata_columns(extra_cols, business_type):
    domain_key = str(business_type or "other").strip().lower()
    relevant = GENERIC_METADATA_COLUMNS | DOMAIN_METADATA_COLUMNS.get(domain_key, set())
    preserved = sorted(col for col in extra_cols if col in relevant)
    ignored = sorted(col for col in extra_cols if col not in relevant)
    return preserved, ignored


def build_extra_payload(row, extra_cols, source_name):
    extras = {}
    for col in extra_cols:
        value = row.get(col)
        if pd.isna(value):
            continue
        value_text = str(value).strip()
        if value_text:
            extras[col] = value_text[:250]
    if not extras:
        return None
    return json.dumps(
        {"source_file": source_name, "extra_columns": extras},
        ensure_ascii=False,
    )


def validate_uploaded_financial_csv(raw_df, source_name="upload.csv", business_type="Other"):
    errors = []
    warnings = []

    if raw_df.empty:
        return None, [f"{source_name}: the CSV file is empty."], warnings

    normalized_columns = [normalize_upload_column(col) for col in raw_df.columns]
    duplicated_columns = sorted({col for col in normalized_columns if normalized_columns.count(col) > 1})
    if duplicated_columns:
        return None, [
            f"{source_name}: duplicate column name(s) after normalization: "
            f"{', '.join(duplicated_columns)}."
        ], warnings

    df = raw_df.copy()
    df.columns = normalized_columns

    missing = REQUIRED_UPLOAD_COLUMNS - set(df.columns)
    if missing:
        errors.append(
            f"{source_name}: missing required column(s): "
            f"{', '.join(sorted(missing))}. Required columns are date, revenue, expenses."
        )
        return None, errors, warnings

    extra_cols = sorted(set(df.columns) - REQUIRED_UPLOAD_COLUMNS - {"orders"})
    preserved_extra_cols, ignored_extra_cols = relevant_metadata_columns(extra_cols, business_type)
    if preserved_extra_cols:
        warnings.append(
            f"{source_name}: relevant additional context preserved as metadata: " + ", ".join(preserved_extra_cols) + "."
        )
    if ignored_extra_cols:
        warnings.append(
            f"{source_name}: unrelated additional column(s) excluded from analysis: " + ", ".join(ignored_extra_cols) + "."
        )

    selected_cols = ["date", "revenue", "expenses"] + (["orders"] if "orders" in df.columns else []) + preserved_extra_cols
    df = df[selected_cols].copy()
    df = df.dropna(subset=["date", "revenue", "expenses"], how="all")
    if df.empty:
        return None, [f"{source_name}: the CSV file has no usable financial rows."], warnings

    parsed_dates = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    bad_date_rows = df[parsed_dates.isna()]
    if not bad_date_rows.empty:
        rows = ", ".join(str(i + 2) for i in bad_date_rows.index[:10])
        errors.append(
            f"{source_name}: invalid date value(s). Use YYYY-MM-DD format. "
            f"Check CSV row(s): {rows}."
        )

    revenue = pd.to_numeric(df["revenue"], errors="coerce")
    expenses = pd.to_numeric(df["expenses"], errors="coerce")
    bad_number_rows = df[revenue.isna() | expenses.isna()]
    if not bad_number_rows.empty:
        rows = ", ".join(str(i + 2) for i in bad_number_rows.index[:10])
        errors.append(
            f"{source_name}: revenue and expenses must be numeric. "
            f"Check CSV row(s): {rows}."
        )

    if "orders" in df.columns:
        orders = pd.to_numeric(df["orders"].fillna(0), errors="coerce")
        bad_order_rows = df[orders.isna()]
        if not bad_order_rows.empty:
            rows = ", ".join(str(i + 2) for i in bad_order_rows.index[:10])
            errors.append(
                f"{source_name}: optional numeric context fields must be numeric when provided. "
                f"Check CSV row(s): {rows}."
            )
    else:
        orders = pd.Series([0] * len(df), index=df.index, dtype="float64")

    infinite_rows = df[
        revenue.isin([float("inf"), float("-inf")])
        | expenses.isin([float("inf"), float("-inf")])
        | orders.isin([float("inf"), float("-inf")])
    ]
    if not infinite_rows.empty:
        rows = ", ".join(str(i + 2) for i in infinite_rows.index[:10])
        errors.append(
            f"{source_name}: required financial fields and optional numeric context must be finite values. "
            f"Check CSV row(s): {rows}."
        )

    negative_rows = df[(revenue < 0) | (expenses < 0) | (orders < 0)]
    if not negative_rows.empty:
        rows = ", ".join(str(i + 2) for i in negative_rows.index[:10])
        errors.append(
            f"{source_name}: required financial fields and optional numeric context cannot be negative. "
            f"Check CSV row(s): {rows}."
        )

    if errors:
        return None, errors, warnings

    clean_df = pd.DataFrame({
        "date": parsed_dates.dt.strftime("%Y-%m-%d"),
        "revenue": revenue.astype(float),
        "expenses": expenses.astype(float),
        "orders": orders.astype(float),
        "source_file": source_name,
    })
    clean_df["extra_data"] = df.apply(
        lambda row: build_extra_payload(row, preserved_extra_cols, source_name),
        axis=1,
    )

    duplicate_dates = clean_df[clean_df.duplicated("date", keep=False)]["date"].unique()
    if len(duplicate_dates) > 0:
        warnings.append(
            f"{source_name}: duplicate date(s) combined into one clean record per date: "
            f"{', '.join(sorted(duplicate_dates)[:10])}."
        )

    clean_df = clean_df.sort_values("date").reset_index(drop=True)
    if clean_df.empty:
        return None, [f"{source_name}: no valid records were found after cleaning the CSV."], warnings
    return clean_df, errors, warnings


def summarize_upload_metadata(group):
    sources = sorted(set(str(value) for value in group["source_file"].dropna()))
    extras = {}
    for payload in group["extra_data"].dropna():
        try:
            parsed = json.loads(payload)
        except (TypeError, ValueError):
            continue
        for key, value in parsed.get("extra_columns", {}).items():
            bucket = extras.setdefault(key, [])
            if value not in bucket and len(bucket) < 5:
                bucket.append(value)
    if not sources and not extras:
        return None
    return json.dumps(
        {
            "source_files": sources,
            "source_rows": int(len(group)),
            "extra_columns": extras,
        },
        ensure_ascii=False,
    )


def combine_uploaded_financial_data(uploaded_files, business_type="Other"):
    errors = []
    warnings = []
    frames = []
    files_with_orders = []

    for uploaded in uploaded_files:
        source_name = uploaded.name
        file_size = getattr(uploaded, "size", None)
        if file_size is None:
            errors.append(f"{source_name}: file size could not be verified. Please re-upload the CSV.")
            continue
        if file_size > MAX_UPLOAD_SIZE_BYTES:
            errors.append(
                f"{source_name}: file exceeds the {MAX_UPLOAD_SIZE_MB} MB per-file upload limit."
            )

    if errors:
        return None, errors[:20], warnings

    for uploaded in uploaded_files:
        source_name = uploaded.name

        try:
            uploaded.seek(0)
            header_df = pd.read_csv(uploaded, nrows=0)
            has_orders = "orders" in [normalize_upload_column(col) for col in header_df.columns]
            uploaded.seek(0)
            chunks = pd.read_csv(uploaded, chunksize=CSV_CHUNK_ROWS)
            file_frames = []
            for chunk in chunks:
                clean_chunk, chunk_errors, chunk_warnings = validate_uploaded_financial_csv(
                    chunk,
                    source_name,
                    business_type,
                )
                errors.extend(chunk_errors)
                warnings.extend(chunk_warnings)
                if clean_chunk is not None:
                    file_frames.append(clean_chunk)
            if file_frames:
                file_df = pd.concat(file_frames, ignore_index=True)
                if has_orders:
                    files_with_orders.append(source_name)
                frames.append(file_df)
        except EmptyDataError:
            errors.append(f"{source_name}: the CSV file is empty or unreadable.")
        except Exception as read_error:
            errors.append(f"{source_name}: could not read CSV file: {read_error}")

    if errors:
        return None, errors[:20], warnings[:20]
    if not frames:
        return None, ["No usable financial rows found in the uploaded file(s)."], warnings[:20]

    combined = pd.concat(frames, ignore_index=True)
    duplicate_dates = combined[combined.duplicated("date", keep=False)]["date"].unique()
    if len(duplicate_dates) > 0:
        warnings.append(
            "Duplicate date(s) across the upload batch were combined into one clean record per date: "
            f"{', '.join(sorted(duplicate_dates)[:12])}."
        )

    grouped_rows = []
    for date_value, group in combined.groupby("date", sort=True):
        grouped_rows.append({
            "date": date_value,
            "revenue": float(group["revenue"].sum()),
            "expenses": float(group["expenses"].sum()),
            "orders": float(group["orders"].sum()),
            "extra_data": summarize_upload_metadata(group),
        })
    clean_df = pd.DataFrame(grouped_rows).sort_values("date").reset_index(drop=True)

    if files_with_orders:
        warnings.append("Relevant optional business context was preserved for: " + ", ".join(sorted(set(files_with_orders))) + ".")

    return clean_df, errors, warnings[:20]


def dataframe_to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")


def dict_to_json_bytes(data):
    return json.dumps(data, indent=2, default=str).encode("utf-8")


def build_summary_export(summary_data):
    return pd.DataFrame([
        {"metric": "Total Revenue", "value": summary_data["revenue"]},
        {"metric": "Total Expenses", "value": summary_data["expenses"]},
        {"metric": "Net Profit / Loss", "value": round(summary_data["revenue"] - summary_data["expenses"], 2)},
        {"metric": "Profit Margin (%)", "value": summary_data["profit_margin"]},
        {"metric": "Current Cash", "value": summary_data["current_cash"]},
        {"metric": "Average Monthly Net", "value": summary_data["avg_monthly_net"]},
        {"metric": "Monthly Burn Rate", "value": summary_data["burn_rate"]},
        {"metric": "Cash Runway Days", "value": summary_data["cash_runway_days"] or "Stable"},
        {"metric": "Risk Score", "value": summary_data["risk_score"]},
        {"metric": "Risk Level", "value": summary_data["risk_level"]},
        {"metric": "Revenue Trend (%)", "value": summary_data["revenue_trend_percent"]},
        {"metric": "Revenue Volatility (%)", "value": summary_data["revenue_volatility_ratio"]},
        {"metric": "Expense Growth (%)", "value": summary_data.get("expense_growth_percent", 0)},
        {"metric": "Loss Streak Months", "value": summary_data.get("loss_streak_months", 0)},
        {"metric": "Cash Coverage Ratio", "value": summary_data.get("cash_coverage_ratio", 0)},
    ])


def build_history_export_df(risk_reports, ai_recommendations):
    rows = []
    for report in risk_reports:
        report_dict = dict(report)
        rows.append({
            "section": "risk_report_history",
            "record_id": report_dict.get("report_id"),
            "date": report_dict.get("generated_at"),
            "metric": report_dict.get("risk_level"),
            "value": report_dict.get("risk_score"),
            "notes": report_dict.get("prediction") or "",
        })
    for recommendation in ai_recommendations:
        rec_dict = dict(recommendation)
        rows.append({
            "section": "ai_recommendation_history",
            "record_id": rec_dict.get("recommendation_id"),
            "date": rec_dict.get("created_at"),
            "metric": f"Report {rec_dict.get('report_id')}",
            "value": rec_dict.get("risk_level"),
            "notes": rec_dict.get("suggestion_text"),
        })
    return pd.DataFrame(rows)


def build_complete_report_csv(summary_data, projected_risk_label, recommendation, risk_reports, ai_recommendations):
    rows = []
    for _, row in build_summary_export(summary_data).iterrows():
        rows.append({
            "section": "current_summary",
            "item": row["metric"],
            "value": row["value"],
            "notes": "",
        })
    rows.extend([
        {"section": "risk_analysis", "item": "Risk Score", "value": summary_data["risk_score"], "notes": "0 low risk, 100 highest risk"},
        {"section": "risk_analysis", "item": "Risk Level", "value": summary_data["risk_level"], "notes": ""},
        {"section": "risk_analysis", "item": "Projected Risk", "value": projected_risk_label, "notes": risk_projection_message(summary_data.get("risk_level"), projected_risk_label)},
    ])
    if recommendation:
        analysis = recommendation.get("analysis", {})
        rows.extend([
            {"section": "ai_insight", "item": "Summary", "value": analysis.get("summary", ""), "notes": ""},
            {"section": "ai_insight", "item": "Key Risk", "value": analysis.get("key_risk", ""), "notes": ""},
            {"section": "ai_insight", "item": "Recommendation", "value": analysis.get("recommendation", ""), "notes": ""},
        ])
    rows.append({"section": "history_snapshot", "item": "Saved Reports", "value": len(risk_reports), "notes": "Current user only"})
    rows.append({"section": "history_snapshot", "item": "Saved AI Recommendations", "value": len(ai_recommendations), "notes": "Current user only"})
    return pd.DataFrame(rows)


def build_current_report_string(summary_data, projected_risk_label, recommendation=None):
    runway = summary_data.get("cash_runway_days")
    runway_display = "Stable (No Burn)" if runway is None else f"{runway} days"
    net = round(summary_data["revenue"] - summary_data["expenses"], 2)
    lines = [
        "ARIA Financial Risk Report",
        "",
        f"Total Revenue: {money(summary_data['revenue'])}",
        f"Total Expenses: {money(summary_data['expenses'])}",
        f"Net Profit / Loss: {money(net)}",
        f"Profit Margin: {summary_data['profit_margin']} %",
        f"Current Cash: {money(summary_data['current_cash'])}",
        f"Average Monthly Net: {money(summary_data['avg_monthly_net'])}",
        f"Burn Rate: {money(summary_data['burn_rate'])}",
        f"Cash Runway: {runway_display}",
        "",
        f"Risk Score: {summary_data['risk_score']} / 100",
        f"Risk Level: {summary_data['risk_level']}",
        f"30-Day Projected Risk: {projected_risk_label}",
        f"Revenue Trend: {summary_data['revenue_trend_percent']} %",
        f"Revenue Volatility: {summary_data['revenue_volatility_ratio']} %",
    ]
    if recommendation:
        analysis = recommendation.get("analysis", {})
        lines.extend([
            "",
            "Recommendation",
            f"Source: {'Groq AI' if recommendation.get('source') == 'groq' else 'Rule-based fallback'}",
            f"Summary: {analysis.get('summary', '')}",
            f"Key Risk: {analysis.get('key_risk', '')}",
            f"Action: {analysis.get('recommendation', '')}",
            f"Urgent Action Required: {analysis.get('urgent_action_required', False)}",
        ])
    return "\n".join(lines)


def build_current_report_text(summary_data, projected_risk_label, recommendation=None):
    return build_current_report_string(summary_data, projected_risk_label, recommendation).encode("utf-8")


def risk_projection_message(current_level, projected_level):
    if projected_level == "Unavailable":
        return "Projected risk is unavailable because the projection model could not complete."
    if current_level == projected_level:
        return f"Projected risk remains {projected_level} based on current financial stability."
    if projected_level == "High":
        return "Projected risk may rise to High; liquidity and cost controls need immediate review."
    if projected_level == "Moderate":
        return "Projected risk may move to Moderate; monitor revenue consistency and expense discipline."
    return "Projected risk may improve to Low if current performance trends continue."


def build_full_export_report_string(summary_data, projected_risk_label, recommendation, risk_reports, ai_recommendations):
    lines = [
        build_current_report_string(summary_data, projected_risk_label, recommendation),
        "",
        "Executive Interpretation",
        risk_projection_message(summary_data.get("risk_level"), projected_risk_label),
        "",
        "History Snapshot",
        f"Saved Risk Reports: {len(risk_reports)}",
        f"Saved AI Recommendations: {len(ai_recommendations)}",
    ]
    if risk_reports:
        latest = dict(risk_reports[0])
        lines.extend([
            f"Latest Saved Report: #{latest.get('report_id')} on {latest.get('generated_at')}",
            f"Latest Saved Risk: {latest.get('risk_level')} ({latest.get('risk_score')}/100)",
        ])
    return "\n".join(lines)


def json_snapshot(data):
    return json.dumps(data or {}, ensure_ascii=False, default=str)


def save_report_with_email(current_user, summary_data, projected_risk_label, recommendation=None):
    report_text = build_current_report_string(summary_data, projected_risk_label, recommendation)
    recipient = current_user.get("email")
    if current_user.get("email_verified") is False:
        raise RuntimeError("Report email requires a verified registered email address.")
    report_id = save_risk_report(
        user_id=current_user["user_id"],
        risk_score=summary_data["risk_score"],
        risk_level=summary_data["risk_level"],
        prediction=f"30-day projected risk: {projected_risk_label}",
        report_text=report_text,
        summary_json=json_snapshot(summary_data),
        recommendation_json=json_snapshot(recommendation),
        email_recipient=recipient,
        email_status="pending",
    )

    try:
        send_report_email(
            recipient_email=recipient,
            report_text=report_text,
            summary=summary_data,
            report_id=report_id,
            recommendation=recommendation,
        )
        update_risk_report_email_status(report_id, "sent")
        return report_id, "sent", None
    except Exception as email_error:
        update_risk_report_email_status(report_id, "not_sent", str(email_error))
        return report_id, "not_sent", str(email_error)


def show_report_save_result(report_id, email_status, email_error=None):
    status_card(f"Risk report saved. Report ID: {report_id}.", "success")
    if email_status == "sent":
        status_card("Report email sent to the registered user email.", "success")
    else:
        status_card("Report saved. Email was not sent; check SMTP settings or delivery status.", "warning")
        if email_error:
            st.caption(email_error)


def build_fallback_recommendation(summary_data, error_message=None):
    risk_level = summary_data.get("risk_level", "Unknown")
    runway = summary_data.get("cash_runway_days")
    margin = summary_data.get("profit_margin", 0)
    trend = summary_data.get("revenue_trend_percent", 0)

    if risk_level == "High" or (runway is not None and runway < 60):
        recommendation = (
            "Prioritize liquidity immediately: review discretionary expenses, "
            "delay non-critical spending, and protect cash runway before growth spending."
        )
        key_risk = "Cash runway or overall risk score is in a critical range."
        urgent = True
    elif margin < 15 or trend < 0:
        recommendation = (
            "Review pricing, receivables, and recurring costs. A focused 5-10% expense "
            "optimization or revenue recovery plan may improve stability."
        )
        key_risk = "Profit margin or revenue trend is weakening."
        urgent = False
    else:
        recommendation = (
            "Maintain current controls, keep monitoring monthly revenue/expense movement, "
            "and save periodic risk reports for trend comparison."
        )
        key_risk = "No immediate high-risk indicator was detected."
        urgent = False

    summary_text = (
        "Fallback recommendation generated from ARIA's rule-based financial metrics "
        "because the AI service is unavailable."
    )

    return {
        "source": "fallback",
        "analysis": {
            "summary": summary_text,
            "key_risk": key_risk,
            "recommendation": recommendation,
            "urgent_action_required": urgent,
            "confidence_score": 60,
        },
        "error": error_message,
        "model_used": "rule-based-fallback",
        "inference_time": None,
    }


def section_header(kicker, title, subtitle=None):
    subtitle_html = f'<div class="aria-section-subtitle">{escape(str(subtitle))}</div>' if subtitle else ""
    anchor = title.lower().replace("&", "and").replace("/", " ").replace("  ", " ").replace(" ", "-")
    st.markdown(
        compact_html(f"""
        <span id="{anchor}"></span>
        <div class="aria-section-kicker">{escape(str(kicker))}</div>
        <div class="aria-section-title">{escape(str(title))}</div>
        {subtitle_html}
        """),
        unsafe_allow_html=True,
    )


def money(value):
    try:
        return f"₹ {float(value):,.0f}"
    except (TypeError, ValueError):
        return "₹ 0"


def compact_html(html):
    return " ".join(line.strip() for line in str(html).splitlines() if line.strip())


def status_card(message, level="info"):
    st.markdown(
        compact_html(
            f"""
            <div class="aria-status aria-status-{escape(str(level))}">
              {escape(str(message))}
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def section_spacer():
    st.markdown('<div class="aria-section-spacer"></div>', unsafe_allow_html=True)


def build_upload_summary(file_count, record_count, file_names, warnings=None, overlaps=None):
    warnings = warnings or []
    overlaps = overlaps or []
    parts = [f"{record_count} clean record(s) ready from {file_count} file(s): {file_names}."]
    if any("preserved" in message.lower() for message in warnings):
        parts.append("Relevant metadata preserved.")
    if any("excluded" in message.lower() or "unrelated" in message.lower() for message in warnings):
        parts.append("Unrelated columns excluded.")
    other_notes = [
        message for message in warnings
        if "preserved" not in message.lower()
        and "excluded" not in message.lower()
        and "unrelated" not in message.lower()
    ]
    if other_notes:
        parts.append(f"{len(other_notes)} additional validation note(s).")
    if overlaps:
        parts.append(f"{len(overlaps)} existing date(s) detected.")
    return " ".join(parts)


def render_history_summary(total_reports, total_recommendations, latest_report=None):
    latest_text = "No saved reports"
    latest_tone = "neutral"
    if latest_report:
        latest_text = f"{latest_report.get('risk_level', 'Unknown')} ({latest_report.get('risk_score', 0)}/100)"
        latest_tone = "risk" if latest_report.get("risk_level") == "High" else "warn" if latest_report.get("risk_level") == "Moderate" else "neutral"
    kpi_grid([
        {"label": "Saved Reports", "value": total_reports, "help": "Unique report_id records for this user", "tone": "neutral"},
        {"label": "Recommendations", "value": total_recommendations, "help": "Unique recommendation_id entries", "tone": "neutral"},
        {"label": "Latest Saved Risk", "value": latest_text, "help": "Most recent saved report", "tone": latest_tone},
    ], secondary=True)


def recommendation_preview(text, limit=140):
    cleaned = " ".join(str(text or "").split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "..."


def kpi_card(label, value, help_text="", tone="default"):
    tone_color = {
        "good": "var(--aria-chart-good)",
        "warn": "var(--aria-chart-risk)",
        "risk": "var(--aria-chart-risk)",
        "neutral": "var(--aria-text)",
        "default": "var(--aria-text)",
    }.get(tone, "var(--aria-text)")
    tone_class = {
        "good": "aria-card-positive",
        "warn": "aria-card-warning",
        "risk": "aria-card-danger",
        "neutral": "aria-card-neutral",
        "default": "aria-card-neutral",
    }.get(tone, "aria-card-neutral")
    st.markdown(
        compact_html(f"""
        <div class="aria-card {tone_class}">
          <div class="aria-card-label">{escape(str(label))}</div>
          <div class="aria-card-value" style="color:{tone_color};">{escape(str(value))}</div>
          <div class="aria-card-help">{escape(str(help_text))}</div>
        </div>
        """),
        unsafe_allow_html=True,
    )


def kpi_grid(cards, secondary=False):
    grid_class = "aria-kpi-grid aria-kpi-grid-secondary" if secondary else "aria-kpi-grid"
    html_cards = []
    for card in cards:
        tone = card.get("tone", "neutral")
        tone_color = {
            "good": "var(--aria-chart-good)",
            "warn": "var(--aria-chart-risk)",
            "risk": "var(--aria-chart-risk)",
            "neutral": "var(--aria-text)",
        }.get(tone, "var(--aria-neutral)")
        tone_class = {
            "good": "aria-card-positive",
            "warn": "aria-card-warning",
            "risk": "aria-card-danger",
            "neutral": "aria-card-neutral",
        }.get(tone, "aria-card-neutral")
        html_cards.append(compact_html(
            f"""
            <div class="aria-card {tone_class}">
              <div class="aria-card-label">{escape(str(card["label"]))}</div>
              <div class="aria-card-value" style="color:{tone_color};">{escape(str(card["value"]))}</div>
              <div class="aria-card-help">{escape(str(card.get("help", "")))}</div>
            </div>
            """
        ))
    st.markdown(compact_html(f'<div class="{grid_class}">{"".join(html_cards)}</div>'), unsafe_allow_html=True)


def empty_state(message):
    st.markdown(
        compact_html(f'<div class="aria-empty">{escape(str(message))}</div>'),
        unsafe_allow_html=True,
    )





def chart_colors():
    if is_dark_theme():
        return {
            "text": "#edf2f7",
            "muted": "#b9c2cf",
            "grid": "#303846",
            "good": "#8fb9a0",
            "warn": "#d19791",
            "risk": "#d19791",
            "neutral": "#a8b3c1",
            "neutral_fill": "rgba(168,179,193,0.16)",
            "template": "plotly_dark",
        }
    return {
        "text": "#17202a",
        "muted": "#667085",
        "grid": "#e4e7ec",
        "good": "#4f7b63",
        "warn": "#8f4b46",
        "risk": "#8f4b46",
        "neutral": "#64748b",
        "neutral_fill": "rgba(100,116,139,0.12)",
        "template": "plotly_white",
    }


def apply_plotly_layout(fig, title, height=380):
    colors = chart_colors()
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=colors["text"])),
        height=height,
        template=colors["template"],
        margin=dict(l=24, r=18, t=56, b=32),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=colors["text"] if not is_dark_theme() else "#111827",
            bordercolor=colors["grid"],
            font=dict(color="#ffffff" if not is_dark_theme() else colors["text"], size=12),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=colors["text"], size=12),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["text"], family="Inter, Segoe UI, sans-serif"),
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor=colors["grid"],
        tickfont=dict(color=colors["muted"], size=12),
        title_font=dict(color=colors["text"], size=13),
        zeroline=False,
    )
    fig.update_yaxes(
        gridcolor=colors["grid"],
        linecolor=colors["grid"],
        tickfont=dict(color=colors["muted"], size=12),
        title_font=dict(color=colors["text"], size=13),
        zerolinecolor=colors["grid"],
    )
    fig.update_annotations(font=dict(color=colors["muted"], size=12))


def chart_config():
    return {
        "displaylogo": False,
        "displayModeBar": False,
        "responsive": True,
        "scrollZoom": False,
        "doubleClick": False,
    }


def risk_class(risk_level):
    return {
        "Low": "aria-risk-low",
        "Moderate": "aria-risk-moderate",
        "High": "aria-risk-high",
    }.get(risk_level, "aria-risk-moderate")


# ==============================
# DATASET UPLOAD  (User Interface Module – Upload Feature)
# ==============================
section_header(
    "Dataset",
    "Upload Financial Data",
    "Validate and save clean records.",
)

st.markdown(
    compact_html(f"""
    <div class="aria-note">
      Required columns: <strong>date</strong>, <strong>revenue</strong>, <strong>expenses</strong>. Max file size: <strong>{MAX_UPLOAD_SIZE_MB} MB per CSV</strong>.
    </div>
    """),
    unsafe_allow_html=True,
)

uploaded_files = st.file_uploader(
    f"Choose CSV file(s) - {MAX_UPLOAD_SIZE_MB} MB max each",
    type=["csv"],
    accept_multiple_files=True,
    help=f"Upload one or more CSV files up to {MAX_UPLOAD_SIZE_MB} MB each.",
)

if uploaded_files:
    clean_df, validation_errors, validation_warnings = combine_uploaded_financial_data(
        uploaded_files,
        current_user.get("business_type", "Other"),
    )

    if validation_errors:
        status_card("Upload validation failed. " + " ".join(validation_errors[:3]), "error")
        st.stop()

    try:
        existing_dates = get_existing_financial_dates(user_id)
    except Exception as date_error:
        st.error(f"Could not check existing saved dates: {date_error}")
        st.stop()
    upload_dates = set(clean_df["date"])
    overlapping_dates = sorted(upload_dates & existing_dates)

    uploaded_names = ", ".join(upload.name for upload in uploaded_files)
    status_card(
        build_upload_summary(
            len(uploaded_files),
            len(clean_df),
            uploaded_names,
            validation_warnings,
            overlapping_dates,
        ),
        "warning" if overlapping_dates else "success",
    )
    if overlapping_dates:
        with st.expander("Show overlapping dates"):
            st.write(", ".join(overlapping_dates[:100]))

    st.caption("Preview of validated records")
    preview_cols = ["date", "revenue", "expenses"]
    st.dataframe(clean_df[preview_cols].head(50), width="stretch", hide_index=True)
    if clean_df["extra_data"].notna().any():
        with st.expander("Additional business context"):
            st.caption("Relevant additional fields are preserved as metadata and excluded from core financial calculations.")
            st.dataframe(clean_df[["date", "extra_data"]].dropna().head(20), width="stretch", hide_index=True)

    replace_existing = False
    if overlapping_dates:
        duplicate_policy = st.radio(
            "Existing date handling",
            ["Skip existing dates and save only new rows", "Replace existing dates with uploaded values"],
            index=0,
        )
        replace_existing = duplicate_policy.startswith("Replace")

    col_up, col_clear = st.columns(2)

    with col_up:
        if st.button("Save Validated Dataset"):
            try:
                records = clean_df.to_dict("records")
                result = save_financial_records(
                    user_id,
                    records,
                    replace_existing=replace_existing,
                )
                status_card(
                    "Dataset saved. "
                    f"Inserted: {result['inserted']} | "
                    f"Updated: {result['updated']} | "
                    f"Skipped existing: {result['skipped']}",
                    "success",
                )
                st.cache_data.clear()
            except Exception as save_error:
                st.error(f"Dataset save failed: {save_error}")

    with col_clear:
        confirm_clear = st.checkbox("Confirm dataset clear", key="confirm_clear_dataset")
        if st.button("Clear My Existing Dataset", disabled=not confirm_clear):
            try:
                delete_financial_data(user_id)
                status_card("Existing financial records were cleared. Upload and save a new dataset.", "warning")
                st.cache_data.clear()
                st.rerun()
            except Exception as clear_error:
                st.error(f"Could not clear dataset: {clear_error}")


section_spacer()


# ==============================
# GENERATE FINANCIAL SUMMARY  (Data Processing Module)
# ==============================
@st.cache_data(ttl=300, show_spinner=False)
def get_summary_cached(uid):
    return generate_financial_summary(uid)


try:
    summary = get_summary_cached(user_id)
except ValueError as ve:
    status_card(str(ve), "info")
    empty_state("Upload a financial dataset above to unlock the dashboard, risk score, charts, advisory, and report history.")
    st.stop()
except Exception as e:
    st.error(f"Error generating financial summary: {e}")
    st.stop()

# Safety key check
required_keys = [
    "revenue", "expenses", "profit_margin", "cash_runway_days",
    "risk_score", "risk_level", "revenue_trend_percent",
    "revenue_volatility_ratio", "revenue_history", "burn_rate",
    "expense_history", "expense_growth_percent", "loss_streak_months",
    "cash_coverage_ratio"
]
for key in required_keys:
    if key not in summary:
        st.error(f"Missing key in summary: {key}")
        st.stop()


# ==============================
# FINANCIAL ANALYSIS REPORT  (Output Screenshot 2)
# ==============================
section_header(
    "Dashboard",
    "Financial Overview",
    "Current financial position.",
)

net = summary["revenue"] - summary["expenses"]

runway          = summary.get("cash_runway_days")
runway_display  = "Stable (No Burn)" if runway is None else f"{runway} days"

margin_tone = "good" if summary["profit_margin"] >= 15 else "warn" if summary["profit_margin"] >= 5 else "risk"
net_tone = "good" if net > 0 else "risk" if net < 0 else "neutral"
runway_tone = "good" if runway is None or runway >= 120 else "warn" if runway and runway >= 60 else "risk"
risk_tone = "risk" if summary["risk_level"] == "High" else "warn" if summary["risk_level"] == "Moderate" else "good"
volatility = summary["revenue_volatility_ratio"]
volatility_tone = "risk" if volatility >= 50 else "warn" if volatility >= 30 else "neutral"
trend = summary["revenue_trend_percent"]
trend_tone = "risk" if trend < 0 else "good" if trend > 0 else "neutral"

kpi_grid([
    {"label": "Revenue", "value": money(summary["revenue"]), "help": "Income captured in uploaded data", "tone": "neutral"},
    {"label": "Expenses", "value": money(summary["expenses"]), "help": "Cost base captured in uploaded data", "tone": "neutral"},
    {"label": "Profit / Loss", "value": money(round(net, 2)), "help": "Revenue minus expenses", "tone": net_tone},
    {"label": "Profit Margin", "value": f"{summary['profit_margin']}%", "help": "Revenue retained after expenses", "tone": margin_tone},
])

kpi_grid([
    {"label": "Cash Position", "value": money(summary["current_cash"]), "help": "Starting cash plus net flow", "tone": "neutral"},
    {"label": "Runway", "value": runway_display, "help": "Estimated survival runway", "tone": runway_tone},
    {"label": "Risk Status", "value": f"{summary['risk_level']} ({summary['risk_score']}/100)", "help": "Composite financial risk score", "tone": risk_tone},
    {"label": "Volatility", "value": f"{volatility}%", "help": "Revenue variability across months", "tone": volatility_tone},
])

kpi_grid([
    {"label": "Average Monthly Net", "value": money(summary["avg_monthly_net"]), "help": "Average monthly cash movement", "tone": "good" if summary["avg_monthly_net"] > 0 else "risk" if summary["avg_monthly_net"] < 0 else "neutral"},
    {"label": "Monthly Burn Rate", "value": money(summary.get("burn_rate", 0)), "help": "Average monthly cash outflow when unprofitable", "tone": "neutral" if summary.get("burn_rate", 0) == 0 else "risk"},
    {"label": "Revenue Trend", "value": f"{trend}%", "help": "Slope of monthly revenue movement", "tone": trend_tone},
], secondary=True)

burn_rate = summary.get("burn_rate", 0)

summary_export_df = build_summary_export(summary)
try:
    projected_risk = project_30_day_risk(summary)
except Exception:
    projected_risk = "Unavailable"

# Interactive Revenue vs Expenses vs Profit chart
labels = ["Total Revenue", "Total Expenses", "Net Profit/Loss"]
values = [summary["revenue"], summary["expenses"], round(net, 2)]
colors = chart_colors()
fig_bar = go.Figure(go.Bar(
    x=labels,
    y=values,
    marker_color=[colors["neutral"], colors["neutral"], colors["good"] if net >= 0 else colors["risk"]],
    marker_line=dict(color=colors["grid"], width=1),
    text=[money(value) for value in values],
    textposition="auto",
    textfont=dict(color="#111827" if is_dark_theme() else "#ffffff", size=12),
    hovertemplate="<b>%{x}</b><br>Amount: ₹ %{y:,.0f}<extra></extra>",
))
apply_plotly_layout(fig_bar, "Financial Overview", height=360)
fig_bar.update_yaxes(title_text="Amount (₹)", tickprefix="₹ ")
st.plotly_chart(fig_bar, width="stretch", config=chart_config())

section_spacer()


# ==============================
# RISK ASSESSMENT DASHBOARD  (Output Screenshot 3)
# ==============================
section_header(
    "Risk",
    "Risk Assessment",
    "Score, benchmark, and 30-day direction.",
)

risk_color_map = {"High": "High", "Moderate": "Moderate", "Low": "Low"}
risk_icon = risk_color_map.get(summary["risk_level"], "Risk")

# Platform benchmark
try:
    platform_avg = get_platform_average_risk(user_id)
except Exception:
    platform_avg = 0

# Risk score visual bar
score = summary["risk_score"]
score_width = max(0, min(int(score), 100))
colors = chart_colors()
bar_color = colors["risk"] if score >= 70 else colors["neutral"] if score >= 35 else colors["good"]
st.markdown(
    compact_html(f"""
    <div class="aria-risk-panel">
      <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;">
        <div>
          <div class="aria-card-label">Current Risk Score</div>
          <div class="aria-card-value">{score} / 100</div>
          <div class="aria-card-help">Lower is healthier. Low: 0-34, Moderate: 35-69, High: 70-100.</div>
        </div>
        <div>
          <span class="aria-risk-badge {risk_class(summary["risk_level"])}">{risk_icon} Risk</span>
          <div class="aria-card-help" style="text-align:right;">Saved average: {platform_avg}</div>
        </div>
      </div>
      <div class="aria-progress">
        <div class="aria-progress-fill" style="width:{score_width}%;background:{bar_color};"></div>
      </div>
    </div>
    """),
    unsafe_allow_html=True
)

with st.expander("How risk score is calculated", expanded=False):
    st.write(
        "ARIA combines profitability, liquidity, revenue direction, expense growth, "
        "cash coverage, volatility, and recent loss streaks. Negative margins, shorter runway, "
        "falling revenue, rising costs, weak cash coverage, high volatility, and consecutive "
        "loss months increase the score. Scores under 35 are Low, 35-69 are Moderate, and 70+ are High."
    )

section_spacer()


# ==============================
# EARLY WARNING  (30-Day Predictive Projection – Algorithm 4)
# ==============================
try:
    projected_risk = project_30_day_risk(summary)
    projection_text = risk_projection_message(summary["risk_level"], projected_risk)
    projection_level = "error" if projected_risk == "High" else "warning" if projected_risk == "Moderate" else "success"
    status_card(projection_text, projection_level)
except Exception as pe:
    status_card(f"Projection unavailable: {pe}", "warning")

section_spacer()


# ==============================
# HISTORICAL TREND GRAPH  (Output Screenshot 5)
# ==============================
st.subheader("Risk Score Trend")

try:
    history = get_risk_history(user_id)
except Exception:
    history = []

if history:
    df_hist = pd.DataFrame(history, columns=["Date", "Risk Score"])
    colors = chart_colors()
    fig_risk = go.Figure()
    fig_risk.add_trace(go.Scatter(
        x=df_hist["Date"],
        y=df_hist["Risk Score"],
        mode="lines+markers",
        name="Risk Score",
        line=dict(color=colors["neutral"], width=2.4),
        marker=dict(size=7, color=colors["neutral"], line=dict(color=colors["grid"], width=1)),
        fill="tozeroy",
        fillcolor=colors["neutral_fill"],
        hovertemplate="<b>%{x}</b><br>Risk Score: %{y}<extra></extra>",
    ))
    fig_risk.add_hline(y=70, line_dash="dash", line_color=colors["risk"], annotation_text="High Risk")
    fig_risk.add_hline(y=35, line_dash="dash", line_color=colors["neutral"], annotation_text="Moderate Risk")
    apply_plotly_layout(fig_risk, "Historical Risk Score Trend", height=380)
    fig_risk.update_xaxes(title_text="Date")
    fig_risk.update_yaxes(title_text="Risk Score", range=[0, 100])
    st.plotly_chart(fig_risk, width="stretch", config=chart_config())

    # Risk worsening detection
    scores = [row[1] for row in history]
    if len(scores) >= 3 and scores[-1] > scores[-2] > scores[-3]:
        status_card("Risk has increased for 3 consecutive periods. Review liquidity and cost controls.", "warning")
else:
    empty_state("No historical risk data yet. Save a risk report to start tracking the trend.")


# ==============================
# REVENUE TREND & VOLATILITY
# ==============================
st.subheader("Revenue Trend and Volatility")

col_t, col_v = st.columns(2)
col_t.metric("Revenue Trend",         f"{summary['revenue_trend_percent']} %")
col_v.metric("Revenue Volatility Ratio", f"{summary['revenue_volatility_ratio']} %")

if summary["revenue_history"]:
    month_labels = summary.get("month_labels", [str(i) for i in range(len(summary["revenue_history"]))])
    expense_history = summary.get("expense_history", [])
    colors = chart_colors()
    revenue_line_color = colors["risk"] if summary["revenue_trend_percent"] < 0 else colors["good"]

    # Plotly Revenue Analysis Chart (Figure 5.1 – Revenue Analysis Result)
    fig_rev = go.Figure()
    fig_rev.add_trace(go.Scatter(
        x=month_labels,
        y=summary["revenue_history"],
        mode="lines+markers",
        name="Revenue (₹)",
        line=dict(color=revenue_line_color, width=2.4),
        marker=dict(size=6, color=revenue_line_color, line=dict(color=colors["grid"], width=1)),
        hovertemplate="<b>%{x}</b><br>Revenue: ₹ %{y:,.0f}<extra></extra>",
    ))
    if expense_history:
        fig_rev.add_trace(go.Scatter(
            x=month_labels,
            y=expense_history,
            mode="lines+markers",
            name="Expenses (₹)",
            line=dict(color=colors["neutral"], width=2.1, dash="dash"),
            marker=dict(size=6, color=colors["neutral"], line=dict(color=colors["grid"], width=1)),
            hovertemplate="<b>%{x}</b><br>Expenses: ₹ %{y:,.0f}<extra></extra>",
        ))
    apply_plotly_layout(fig_rev, "Revenue vs Expenses Trend")
    fig_rev.update_xaxes(title_text="Month")
    fig_rev.update_yaxes(title_text="Amount (₹)")
    st.plotly_chart(fig_rev, width="stretch", config=chart_config())
else:
    empty_state("Not enough revenue data for the trend graph.")

section_spacer()


# ==============================
# AI FINANCIAL ADVISORY  (Output Screenshot 4 – Algorithm 5)
# ==============================
section_header(
    "Advisory",
    "AI Financial Advisory",
    "Generate focused financial recommendations.",
)

if st.button("Generate AI Insight"):
    with st.spinner("Generating AI insight..."):
        try:
            ai_result = generate_ai(summary)
        except Exception as ai_err:
            ai_result = {
                "success": False,
                "error": str(ai_err),
                "model_used": "unavailable",
                "inference_time": None,
            }

    if isinstance(ai_result, dict) and ai_result.get("success"):
        st.session_state.latest_recommendation = {
            "source": "groq",
            "analysis": ai_result.get("analysis", {}),
            "error": None,
            "model_used": ai_result.get("model_used"),
            "inference_time": ai_result.get("inference_time"),
        }
    else:
        error_msg = ai_result.get("error", "Unknown error") if ai_result else "No response"
        status_card("AI advisory is unavailable in this environment. Rule-based recommendation generated.", "info")
        st.session_state.latest_recommendation = build_fallback_recommendation(summary, error_msg)

latest_recommendation = st.session_state.latest_recommendation

if latest_recommendation:
    analysis = latest_recommendation.get("analysis", {})

    source_label = "Groq AI" if latest_recommendation.get("source") == "groq" else "Rule-based fallback"
    st.caption(
        f"Source: {source_label} | Model: {latest_recommendation.get('model_used')} | "
        f"Inference Time: {latest_recommendation.get('inference_time') or 'n/a'}"
    )

    col_ai_1, col_ai_2 = st.columns(2)
    with col_ai_1:
        st.markdown("**Summary**")
        status_card(analysis.get("summary", ""), "info")
        st.markdown("**Key Risk**")
        status_card(analysis.get("key_risk", ""), "warning")
    with col_ai_2:
        st.markdown("**Recommendation**")
        status_card(analysis.get("recommendation", ""), "info")
        urgent = analysis.get("urgent_action_required", False)
        st.markdown("**Urgent Action Required**")
        if urgent:
            status_card("Yes - review this business immediately.", "error")
        else:
            status_card("No - situation appears manageable.", "info")

    try:
        conf = int(analysis.get("confidence_score", 0))
    except (TypeError, ValueError):
        conf = 0
    conf = max(0, min(conf, 95))
    st.progress(conf / 95 if conf else 0, text=f"Confidence: {conf} / 95")

    if st.button("Save Recommendation"):
        try:
            suggestion = (
                f"Source: {source_label}\n"
                f"Summary: {analysis.get('summary', '')}\n"
                f"Key Risk: {analysis.get('key_risk', '')}\n"
                f"Recommendation: {analysis.get('recommendation', '')}\n"
                f"Urgent Action Required: {analysis.get('urgent_action_required', False)}\n"
                f"Confidence Score: {analysis.get('confidence_score', '')}"
            )
            pred_label = project_30_day_risk(summary)
            rid, email_status, email_error = save_report_with_email(
                current_user,
                summary,
                pred_label,
                latest_recommendation,
            )
            save_ai_recommendation(rid, suggestion)
            status_card("Recommendation saved to history.", "success")
            show_report_save_result(rid, email_status, email_error)
        except Exception as save_err:
            st.error(f"Save failed: {save_err}")

section_spacer()


# ==============================
# REPORT AND RECOMMENDATION HISTORY
# ==============================
section_header(
    "History",
    "Reports and Recommendations",
    "Saved reports and recommendations.",
)
st.caption("Saved reports and recommendations are retained for this signed-in business.")

try:
    risk_reports = get_risk_reports(user_id)
    ai_recommendations = get_ai_recommendations_for_user(user_id)
except Exception as history_error:
    st.error(f"Could not load report history: {history_error}")
    risk_reports = []
    ai_recommendations = []

history_tab, recommendation_tab = st.tabs([
    "Risk Reports",
    "AI Recommendations",
])

with history_tab:
    if risk_reports:
        risk_report_df = pd.DataFrame([dict(row) for row in risk_reports])
        render_history_summary(len(risk_report_df), len(ai_recommendations), risk_report_df.iloc[0].to_dict())
        visible_report_cols = [
            "report_id", "generated_at", "risk_level", "risk_score",
            "prediction", "email_status", "email_recipient",
        ]
        report_view_df = (
            risk_report_df[visible_report_cols]
            .rename(columns={
                "report_id": "Report ID",
                "generated_at": "Saved At",
                "risk_level": "Risk Level",
                "risk_score": "Risk Score",
                "prediction": "Projection",
                "email_status": "Email",
                "email_recipient": "Recipient",
            })
        )
        st.dataframe(
            report_view_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Risk Score": st.column_config.ProgressColumn(
                    "Risk Score",
                    min_value=0,
                    max_value=100,
                    format="%.0f",
                ),
            },
        )
        report_labels = {
            row["report_id"]: f"Report ID {row['report_id']} | {row['generated_at']} | {row['risk_level']} ({row['risk_score']}/100)"
            for _, row in risk_report_df.iterrows()
        }
        selected_history_report = st.selectbox(
            "View saved report details",
            risk_report_df["report_id"].tolist(),
            format_func=lambda rid: report_labels.get(rid, f"Report {rid}"),
            key="selected_history_report",
        )
        selected_report_row = risk_report_df[risk_report_df["report_id"] == selected_history_report].iloc[0].to_dict()
        with st.expander("Selected report summary", expanded=True):
            report_text = selected_report_row.get("report_text") or json.dumps(selected_report_row, indent=2, default=str)
            selected_risk_score = selected_report_row.get("risk_score", 0)
            selected_risk_level = selected_report_row.get("risk_level", "Unknown")
            selected_email_status = selected_report_row.get("email_status", "not_sent")
            st.markdown(
                compact_html(f"""
                <div class="aria-exec-panel">
                  <h4>Executive Summary</h4>
                  <p><strong>Report #{escape(str(selected_history_report))}</strong> recorded a
                  <strong>{escape(str(selected_risk_level))}</strong> risk level with a score of
                  <strong>{escape(str(selected_risk_score))}/100</strong>.</p>
                  <p>{escape(str(selected_report_row.get("prediction") or "No projection note was saved."))}</p>
                  <p>Email status: <strong>{escape(str(selected_email_status))}</strong></p>
                </div>
                """),
                unsafe_allow_html=True,
            )
            st.progress(
                min(max(float(selected_risk_score or 0), 0), 100) / 100,
                text=f"Saved risk score: {selected_risk_score}/100",
            )
            st.text_area("Readable report notes", value=report_text, height=180, disabled=True)
    else:
        risk_report_df = pd.DataFrame()
        empty_state("No saved risk reports yet. Save the current risk report to start history tracking.")

with recommendation_tab:
    if ai_recommendations:
        recommendation_df = pd.DataFrame([dict(row) for row in ai_recommendations])
        render_history_summary(len(risk_reports), len(recommendation_df), dict(risk_reports[0]) if risk_reports else None)
        recommendation_view_df = pd.DataFrame({
            "Recommendation ID": recommendation_df["recommendation_id"],
            "Report ID": recommendation_df["report_id"],
            "Saved At": recommendation_df["created_at"],
            "Risk Level": recommendation_df["risk_level"],
            "Risk Score": recommendation_df["risk_score"],
            "Recommendation Preview": recommendation_df["suggestion_text"].apply(recommendation_preview),
        })
        st.dataframe(
            recommendation_view_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Risk Score": st.column_config.ProgressColumn(
                    "Risk Score",
                    min_value=0,
                    max_value=100,
                    format="%.0f",
                ),
            },
        )

        selected_report_ids = sorted(recommendation_df["report_id"].unique().tolist())
        selected_report = st.selectbox(
            "View recommendation details for Report ID",
            selected_report_ids,
        )
        selected_rows = recommendation_df[recommendation_df["report_id"] == selected_report]
        for _, row in selected_rows.iterrows():
            with st.expander(f"Recommendation ID {row['recommendation_id']} | {row['created_at']}"):
                st.text(row["suggestion_text"])
    else:
        recommendation_df = pd.DataFrame()
        empty_state("No saved AI recommendations yet.")

section_header(
    "Export",
    "Export / Download Report",
    "Download current analysis and history.",
)

complete_report_text = build_full_export_report_string(
    summary,
    projected_risk,
    st.session_state.latest_recommendation,
    risk_reports,
    ai_recommendations,
)
complete_report_csv = build_complete_report_csv(
    summary,
    projected_risk,
    st.session_state.latest_recommendation,
    risk_reports,
    ai_recommendations,
)
history_snapshot_df = build_history_export_df(risk_reports, ai_recommendations)

st.markdown(
    compact_html("""
    <div class="aria-note">
      The consolidated report includes current summary metrics, risk interpretation,
      AI insight when available, and a compact snapshot of saved history.
    </div>
    """),
    unsafe_allow_html=True,
)

export_col_1, export_col_2, export_col_3 = st.columns(3)
with export_col_1:
    st.download_button(
        "Download Complete Report TXT",
        data=complete_report_text.encode("utf-8"),
        file_name="aria_complete_report.txt",
        mime="text/plain",
        key="download_complete_report_txt",
    )
with export_col_2:
    st.download_button(
        "Download Report Data CSV",
        data=dataframe_to_csv_bytes(complete_report_csv),
        file_name="aria_complete_report_data.csv",
        mime="text/csv",
        key="download_complete_report_csv",
    )
with export_col_3:
    st.download_button(
        "Download History Snapshot CSV",
        data=dataframe_to_csv_bytes(history_snapshot_df),
        file_name="aria_history_snapshot.csv",
        mime="text/csv",
        key="download_history_snapshot_csv",
        disabled=history_snapshot_df.empty,
    )

if st.button("Save Report and Send Email", key="save_report_from_export"):
    try:
        rid, email_status, email_error = save_report_with_email(
            current_user,
            summary,
            projected_risk,
            st.session_state.latest_recommendation,
        )
        show_report_save_result(rid, email_status, email_error)
    except Exception as save_err:
        st.error(f"Failed to save report: {save_err}")

section_spacer()


# ==============================
# WHAT-IF FINANCIAL SIMULATION
# ==============================
section_header(
    "Simulation",
    "What-If Financial Simulation",
    "Stress-test revenue and expense changes.",
)

rev_change = st.slider("Revenue Change (%)",  -30, 30, 0, key="rev_slider")
exp_change = st.slider("Expense Change (%)", -30, 30, 0, key="exp_slider")
st.caption("Simulation applies changes to the current uploaded financial period and does not overwrite saved financial data.")

if st.button("Run Simulation"):
    try:
        sim = simulate_scenario(summary, rev_change, exp_change)
    except Exception as sim_err:
        st.error(f"Simulation failed: {sim_err}")
        st.stop()

    st.write("#### Simulation Results")

    s1, s2, s3 = st.columns(3)
    s1.metric("Projected Revenue",    money(sim["simulated_revenue"]))
    s2.metric("Projected Expenses",   money(sim["simulated_expenses"]))
    s3.metric("Projected Profit/Loss", money(sim["simulated_profit"]))

    s4, s5, s6 = st.columns(3)
    s4.metric("Projected Profit Margin", f"{sim['simulated_profit_margin']} %")
    s5.metric("Projected Cash Position", money(sim["simulated_cash_position"]))

    sim_runway = sim.get("simulated_runway_days")
    s6.metric("Projected Runway", "Stable" if sim_runway is None else f"{sim_runway} days")

    sim_delta = sim["simulated_risk_score"] - summary["risk_score"]
    sim_direction = "increase" if sim_delta > 0 else "decrease" if sim_delta < 0 else "remain stable"
    status_card(
        f"Projected risk becomes {sim['simulated_risk_level']} with a score of "
        f"{sim['simulated_risk_score']}/100. This would {sim_direction} versus the current score.",
        "error" if sim["simulated_risk_level"] == "High" else "warning" if sim["simulated_risk_level"] == "Moderate" else "success",
    )

section_spacer()
st.caption("ARIA – Advanced Risk Intelligence Assistant | JECRC University, Jaipur | 2025–26")
