"""Theme and chart styling helpers for the ARIA Streamlit UI."""


def _streamlit_module(streamlit_module=None):
    if streamlit_module is not None:
        return streamlit_module
    import streamlit as st

    return st


def is_dark_theme(streamlit_module=None) -> bool:
    st = _streamlit_module(streamlit_module)
    wp = st.session_state.get("wallpaper_theme", "None")
    if wp in ["Cosmic Nebula", "Midnight Stars", "Cyber Grid"]:
        return True
    elif wp in ["Morning Sky", "Minimal Starlet", "Architect Grid"]:
        return False
    try:
        return st.context.theme.type == "dark"
    except Exception:
        try:
            return st.get_option("theme.base") == "dark"
        except Exception:
            return False


def _theme_tokens(streamlit_module=None) -> dict:
    if is_dark_theme(streamlit_module):
        return {
            "bg": "#0f141a",
            "panel": "#151b23",
            "panel_soft": "#1d2430",
            "text": "#edf2f7",
            "muted": "#b9c2cf",
            "subtle": "#8d99a8",
            "border": "#303846",
            "border_strong": "#465164",
            "accent": "#9aa4b2",
            "accent_soft": "#202735",
            "good": "#8fb9a0",
            "warn": "#e2a38f",
            "risk": "#d19791",
            "neutral": "#a8b3c1",
            "good_soft": "rgba(143, 185, 160, 0.14)",
            "warn_soft": "rgba(226, 163, 143, 0.14)",
            "risk_soft": "rgba(209, 151, 145, 0.14)",
            "neutral_soft": "rgba(168, 179, 193, 0.16)",
            "template": "plotly_dark",
        }
    return {
        "bg": "#f7f8fa",
        "panel": "#ffffff",
        "panel_soft": "#f3f5f7",
        "text": "#17202a",
        "muted": "#667085",
        "subtle": "#98a2b3",
        "border": "#e4e7ec",
        "border_strong": "#d0d5dd",
        "accent": "#475467",
        "accent_soft": "#f2f4f7",
        "good": "#3f7155",
        "warn": "#9b5f22",
        "risk": "#9a3f3a",
        "neutral": "#64748b",
        "good_soft": "rgba(63, 113, 85, 0.11)",
        "warn_soft": "rgba(155, 95, 34, 0.12)",
        "risk_soft": "rgba(154, 63, 58, 0.12)",
        "neutral_soft": "rgba(100, 116, 139, 0.12)",
        "template": "plotly_white",
    }


def apply_global_theme(streamlit_module=None) -> None:
    st = _streamlit_module(streamlit_module)
    tokens = _theme_tokens(st)
    st.markdown(
        f"""
        <style>
          :root {{
            --aria-bg: {tokens["bg"]};
            --aria-panel: {tokens["panel"]};
            --aria-panel-soft: {tokens["panel_soft"]};
            --aria-text: {tokens["text"]};
            --aria-muted: {tokens["muted"]};
            --aria-subtle: {tokens["subtle"]};
            --aria-border: {tokens["border"]};
            --aria-border-strong: {tokens["border_strong"]};
            --aria-accent: {tokens["accent"]};
            --aria-accent-soft: {tokens["accent_soft"]};
            --aria-good: {tokens["good"]};
            --aria-warn: {tokens["warn"]};
            --aria-risk: {tokens["risk"]};
            --aria-neutral: {tokens["neutral"]};
            --aria-good-soft: {tokens["good_soft"]};
            --aria-warn-soft: {tokens["warn_soft"]};
            --aria-risk-soft: {tokens["risk_soft"]};
            --aria-neutral-soft: {tokens["neutral_soft"]};
            --aria-shadow: none;
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

          .aria-card,
          .aria-exec-panel,
          .aria-risk-panel {{
            background: var(--aria-panel);
            border: 1px solid var(--aria-border);
            border-radius: 8px;
            box-shadow: var(--aria-shadow);
          }}

          .aria-card {{
            padding: 14px;
            min-height: 112px;
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

          .aria-card-positive {{ border-left-color: var(--aria-good); }}
          .aria-card-danger {{ border-left-color: var(--aria-risk); }}
          .aria-card-warning {{ border-left-color: var(--aria-warn); }}

          .aria-exec-panel {{
            padding: 14px;
            margin: 8px 0 12px;
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
            padding: 15px;
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
            background: var(--aria-good-soft);
            color: var(--aria-good);
            border-color: var(--aria-good);
          }}

          .aria-risk-moderate {{
            background: var(--aria-warn-soft);
            color: var(--aria-warn);
            border-color: var(--aria-warn);
          }}

          .aria-risk-high {{
            background: var(--aria-risk-soft);
            color: var(--aria-risk);
            border-color: var(--aria-risk);
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

          .aria-note,
          .aria-status {{
            background: transparent;
            border: 1px solid var(--aria-border);
            border-radius: 8px;
            color: var(--aria-text);
          }}

          .aria-note {{
            color: var(--aria-muted);
            padding: 9px 11px;
            margin-bottom: 10px;
            font-size: 0.86rem;
          }}

          .aria-status {{
            border-left: 2px solid var(--aria-neutral);
            padding: 8px 10px;
            margin: 8px 0;
            font-size: 0.86rem;
            line-height: 1.45;
          }}

          .aria-status-info {{ border-left-color: var(--aria-neutral); }}
          .aria-status-success {{ border-left-color: var(--aria-good); }}
          .aria-status-warning {{ border-left-color: var(--aria-warn); }}
          .aria-status-error,
          .aria-status-danger {{ border-left-color: var(--aria-risk); }}

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
            font-size: 1.15rem;
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
          .stSelectbox div[data-baseweb="select"],
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
            overflow: auto;
          }}

          hr {{
            margin: 1rem 0;
            border-color: var(--aria-border);
            opacity: 0.45;
          }}

          .aria-section-spacer {{
            height: 18px;
          }}

          @media (max-width: 760px) {{
            .main .block-container {{
              padding-left: 1rem;
              padding-right: 1rem;
              max-width: 100%;
            }}

            div[data-testid="stHorizontalBlock"] {{
              flex-direction: column;
              gap: 0.75rem;
            }}

            div[data-testid="column"] {{
              width: 100% !important;
              flex: 1 1 100% !important;
              min-width: 100% !important;
            }}

            .aria-hero {{
              padding: 14px 0 16px;
            }}

            .aria-hero h1 {{
              font-size: 1.45rem;
            }}

            .aria-card {{
              min-height: auto;
              padding: 14px;
            }}

            .aria-kpi-grid,
            .aria-kpi-grid-secondary,
            .aria-history-summary {{
              grid-template-columns: 1fr;
            }}

            .aria-card-value {{
              font-size: 1.12rem;
            }}

            .stTabs [data-baseweb="tab-list"] {{
              overflow-x: auto;
              flex-wrap: nowrap;
            }}

            .stButton > button,
            .stDownloadButton > button {{
              width: 100%;
            }}
          }}

          @media (min-width: 761px) and (max-width: 1100px) {{
            .aria-kpi-grid,
            .aria-kpi-grid-secondary,
            .aria-history-summary {{
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
          }}

          @media (min-width: 1600px) {{
            .main .block-container {{
              max-width: 1480px;
            }}
          }}
        </style>

        <div class="aria-hero">
          <h1>ARIA - Advanced Risk Intelligence Assistant</h1>
          <p>Business Risk Intelligence</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_runtime_theme_overrides(streamlit_module=None) -> None:
    """Applies Streamlit-theme-aware variables and mobile layout fixes."""
    st = _streamlit_module(streamlit_module)
    is_dark = is_dark_theme(st)
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
    good = "#8fb9a0" if is_dark else "#3f7155"
    warn = "#e2a38f" if is_dark else "#9b5f22"
    risk = "#d19791" if is_dark else "#9a3f3a"
    neutral = "#a8b3c1" if is_dark else "#64748b"
    chart_good = "#8fb9a0" if is_dark else "#3f7155"
    chart_risk = "#d19791" if is_dark else "#9a3f3a"
    chart_neutral = "#a8b3c1" if is_dark else "#64748b"

    st.markdown(
        f"""
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

          /* Hide Streamlit Community Cloud UI Elements (GitHub, Fork) */
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

          @media (max-width: 760px) {{
            div[data-testid="stHorizontalBlock"] {{
              flex-direction: column;
              gap: 0.75rem;
            }}

            div[data-testid="column"] {{
              width: 100% !important;
              flex: 1 1 100% !important;
              min-width: 100% !important;
            }}

            .stButton > button,
            .stDownloadButton > button {{
              width: 100%;
            }}
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
        </style>
        """,
        unsafe_allow_html=True,
    )



def chart_colors(streamlit_module=None) -> dict:
    tokens = _theme_tokens(streamlit_module)
    return {
        "text": tokens["text"],
        "muted": tokens["muted"],
        "grid": tokens["border"],
        "good": tokens["good"],
        "warn": tokens["warn"],
        "risk": tokens["risk"],
        "neutral": tokens["neutral"],
        "neutral_fill": tokens["neutral_soft"],
        "template": tokens["template"],
    }


def apply_plotly_layout(fig, title, height=380, streamlit_module=None):
    colors = chart_colors(streamlit_module)
    dark = is_dark_theme(streamlit_module)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=colors["text"])),
        height=height,
        template=colors["template"],
        margin=dict(l=24, r=18, t=56, b=32),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#111827" if dark else colors["text"],
            bordercolor=colors["grid"],
            font=dict(color=colors["text"] if dark else "#ffffff", size=12),
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


def chart_config() -> dict:
    return {
        "displaylogo": False,
        "displayModeBar": False,
        "responsive": True,
        "scrollZoom": False,
        "doubleClick": False,
    }
