"""Visual theme: palette constants and CSS injection for a unified look."""

PALETTE = {
    "primary": "#0F4C81",
    "primary_dark": "#083358",
    "secondary": "#3B82A8",
    "accent": "#D97706",
    "success": "#059669",
    "danger": "#B91C1C",
    "neutral": "#64748B",
    "surface": "#FFFFFF",
    "surface_muted": "#F5F7FA",
    "border": "#E2E8F0",
    "text": "#1B2A3A",
    "text_muted": "#64748B",
}

CHART_SEQUENCE = [
    PALETTE["primary"],
    PALETTE["secondary"],
    PALETTE["accent"],
    PALETTE["success"],
    PALETTE["neutral"],
]

CHART_SCALE_BLUE = [
    [0.00, "#E8EEF4"],
    [0.25, "#B5C8DB"],
    [0.50, "#6E93B6"],
    [0.75, "#285F8F"],
    [1.00, PALETTE["primary_dark"]],
]

CHART_SCALE_WARM = [
    [0.00, "#FEF3E8"],
    [0.25, "#FCD5A1"],
    [0.50, "#F1A159"],
    [0.75, "#C66B12"],
    [1.00, "#7A3F03"],
]


CUSTOM_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}

    /* Hide Streamlit defaults */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header [data-testid="stHeader"] {{background: transparent;}}

    /* Main container spacing */
    .block-container {{
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }}

    /* Page header */
    .dsgr-header {{
        padding: 1.5rem 0 1rem 0;
        border-bottom: 1px solid {PALETTE['border']};
        margin-bottom: 2rem;
    }}
    .dsgr-header h1 {{
        font-size: 1.75rem;
        font-weight: 700;
        color: {PALETTE['primary_dark']};
        margin: 0;
        letter-spacing: -0.02em;
    }}
    .dsgr-header .subtitle {{
        color: {PALETTE['text_muted']};
        font-size: 0.95rem;
        margin-top: 0.25rem;
    }}
    .dsgr-pill {{
        display: inline-block;
        background: {PALETTE['surface_muted']};
        color: {PALETTE['text_muted']};
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 500;
        letter-spacing: 0.02em;
    }}

    /* KPI cards */
    .dsgr-kpi {{
        background: {PALETTE['surface']};
        border: 1px solid {PALETTE['border']};
        border-radius: 10px;
        padding: 1.1rem 1.25rem;
        transition: border-color 0.15s;
    }}
    .dsgr-kpi:hover {{
        border-color: {PALETTE['secondary']};
    }}
    .dsgr-kpi .label {{
        color: {PALETTE['text_muted']};
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.35rem;
    }}
    .dsgr-kpi .value {{
        color: {PALETTE['primary_dark']};
        font-size: 1.6rem;
        font-weight: 700;
        line-height: 1.1;
        letter-spacing: -0.02em;
    }}
    .dsgr-kpi .delta {{
        color: {PALETTE['text_muted']};
        font-size: 0.8rem;
        margin-top: 0.3rem;
    }}

    /* Section heading */
    .dsgr-section {{
        font-size: 1.05rem;
        font-weight: 600;
        color: {PALETTE['text']};
        margin: 1.5rem 0 0.75rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid {PALETTE['primary']};
        display: inline-block;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 2rem;
        border-bottom: 1px solid {PALETTE['border']};
    }}
    .stTabs [data-baseweb="tab"] {{
        font-weight: 500;
        color: {PALETTE['text_muted']};
        padding: 0.5rem 0;
    }}
    .stTabs [aria-selected="true"] {{
        color: {PALETTE['primary']};
    }}

    /* Buttons */
    .stButton > button {{
        border-radius: 8px;
        font-weight: 500;
        border: 1px solid {PALETTE['border']};
        transition: all 0.15s;
    }}
    .stButton > button[kind="primary"] {{
        background: {PALETTE['primary']};
        border-color: {PALETTE['primary']};
    }}
    .stButton > button[kind="primary"]:hover {{
        background: {PALETTE['primary_dark']};
        border-color: {PALETTE['primary_dark']};
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background: {PALETTE['surface_muted']};
        border-right: 1px solid {PALETTE['border']};
    }}
    [data-testid="stSidebar"] h2 {{
        color: {PALETTE['primary_dark']};
        font-size: 1rem;
        font-weight: 600;
    }}

    /* Dataframe */
    [data-testid="stDataFrame"] {{
        border: 1px solid {PALETTE['border']};
        border-radius: 8px;
        overflow: hidden;
    }}

    /* Legend chips */
    .dsgr-legend {{
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
        font-size: 0.85rem;
        color: {PALETTE['text_muted']};
    }}
    .dsgr-legend-item {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
    }}
    .dsgr-legend-swatch {{
        width: 12px;
        height: 12px;
        border-radius: 3px;
        display: inline-block;
    }}

    /* Footer */
    .dsgr-footer {{
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid {PALETTE['border']};
        color: {PALETTE['text_muted']};
        font-size: 0.8rem;
        text-align: center;
    }}
</style>
"""


def kpi_card(label, value, delta=None):
    """Render a professional KPI card (HTML string for st.markdown)."""
    delta_html = f'<div class="delta">{delta}</div>' if delta else ""
    return f"""
<div class="dsgr-kpi">
    <div class="label">{label}</div>
    <div class="value">{value}</div>
    {delta_html}
</div>
""".strip()


def section_title(text):
    """Inline section heading with brand underline."""
    return f'<div class="dsgr-section">{text}</div>'
