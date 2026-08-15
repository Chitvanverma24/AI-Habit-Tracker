"""

AI Habit Tracker SaaS
Commercial Production Design System — Linear / Vercel / Notion Quality

"""

import streamlit as st


def inject_global_css():
    """Injects global CSS for a production commercial SaaS experience."""
    st.markdown("""
    <style>
    /* ===== Google Fonts ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    /* ===== Color Palette & Tokens ===== */
    :root {
        --primary: #2563eb;
        --primary-hover: #1d4ed8;
        --primary-light: rgba(37, 99, 235, 0.08);
        --accent-indigo: #4f46e5;
        --success: #059669;
        --success-light: rgba(5, 150, 105, 0.08);
        --warning: #d97706;
        --warning-light: rgba(217, 119, 6, 0.08);
        --danger: #dc2626;
        --danger-light: rgba(220, 38, 38, 0.08);

        /* Backgrounds */
        --bg-page: #f8fafc;
        --bg-surface: #ffffff;
        --bg-sidebar: #0f172a;
        --bg-sidebar-hover: #1e293b;
        --bg-sidebar-active: #2563eb;

        /* Borders & Separators */
        --border-color: #e2e8f0;
        --border-hover: #cbd5e1;
        --border-sidebar: #1e293b;

        /* Typography */
        --text-primary: #0f172a;
        --text-secondary: #334155;
        --text-muted: #64748b;
        --text-sidebar: #ffffff;
        --text-sidebar-muted: #f8fafc;

        /* Radius & Shadows */
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --shadow-xs: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.08), 0 1px 2px -1px rgba(0, 0, 0, 0.08);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.05);
    }

    /* ===== Global App Setup & Content Separator ===== */
    .stApp {
        background-color: var(--bg-page);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--text-primary);
    }

    #MainMenu, footer { visibility: hidden; }

    /* Hide the default Streamlit header toolbar elements but keep the sidebar toggle button visible */
    header[data-testid="stHeader"] {
        background: transparent !important;
        backdrop-filter: none !important;
    }
    header[data-testid="stHeader"] .stToolbar {
        display: none !important;
    }

    /* Main Content Padding & Max Width */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        padding-left: 2.5rem !important;
        padding-right: 2.5rem !important;
        max-width: 1320px !important;
    }

    /* ===== Typography ===== */
    h1, h2, h3, h4, h5, h6,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Inter', sans-serif !important;
        color: #0f172a !important;
        font-weight: 700 !important;
        letter-spacing: -0.025em !important;
    }

    p, span, li, label, .stMarkdown p {
        font-family: 'Inter', sans-serif;
        color: #334155;
        font-size: 0.95rem;
        line-height: 1.55;
    }

    /* ===== Premium Dark Sidebar (Linear / Vercel Grade) ===== */
    [data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b !important;
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.12) !important;
    }

    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        padding: 1.25rem 0.85rem !important;
        gap: 0.45rem !important;
    }

    /* Sidebar Headings - Bright White */
    .nav-section-label {
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        color: #ffffff !important;
        text-transform: uppercase !important;
        letter-spacing: 0.09em !important;
        padding: 0.75rem 0.35rem 0.35rem 0.35rem !important;
    }

    /* Sidebar User Info Text */
    .sidebar-user-title {
        font-weight: 800 !important;
        color: #ffffff !important;
        font-size: 0.95rem !important;
    }
    .sidebar-user-email {
        font-size: 0.78rem !important;
        color: #f8fafc !important;
        font-weight: 500 !important;
    }

    /* Sidebar Navigation Items (Buttons) */
    [data-testid="stSidebar"] .stButton > button {
        background-color: transparent !important;
        color: #ffffff !important;
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        padding: 0.65rem 0.95rem !important;
        text-align: left !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        width: 100% !important;
        box-shadow: none !important;
    }

    /* Inactive Sidebar Hover */
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #1e293b !important;
        color: #ffffff !important;
        border-color: #3b82f6 !important;
        transform: translateX(4px) !important;
    }

    /* Active Sidebar Button */
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.45) !important;
        transform: none !important;
    }

    [data-testid="stSidebar"] hr {
        border-color: #1e293b !important;
        margin: 0.85rem 0 !important;
    }

    /* ===== Buttons & Bright White Contrast Rules (All States) ===== */
    .stButton > button {
        border-radius: var(--radius-sm) !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9rem !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        letter-spacing: -0.01em !important;
        border: 1.5px solid #cbd5e1 !important;
        color: #0f172a !important;
        background-color: #ffffff !important;
        padding: 0.55rem 1.1rem !important;
        box-shadow: var(--shadow-xs) !important;
    }

    /* Secondary Buttons Hover State — Dark Slate Background & Bright White Text */
    .stButton > button:hover,
    .stButton > button:focus,
    .stButton > button:active {
        background-color: #1e293b !important;
        border-color: #3b82f6 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.2) !important;
        transform: translateY(-1px) !important;
    }

    .stButton > button:hover *,
    .stButton > button:focus *,
    .stButton > button:active * {
        color: #ffffff !important;
    }

    /* Primary Action Buttons — Bright Blue Gradient with Pure White Text */
    .stButton > button[kind="primary"],
    [data-testid="stFormSubmitButton"] > button,
    [data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        border: 1px solid #1d4ed8 !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        box-shadow: 0 3px 10px rgba(37, 99, 235, 0.35) !important;
    }

    .stButton > button[kind="primary"] *,
    [data-testid="stFormSubmitButton"] > button *,
    [data-testid="stFormSubmitButton"] button * {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    .stButton > button[kind="primary"]:hover,
    .stButton > button[kind="primary"]:focus,
    .stButton > button[kind="primary"]:active,
    [data-testid="stFormSubmitButton"] > button:hover,
    [data-testid="stFormSubmitButton"] > button:focus,
    [data-testid="stFormSubmitButton"] > button:active {
        background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.5) !important;
        transform: translateY(-1px) !important;
        color: #ffffff !important;
    }

    .stButton > button[kind="primary"]:hover *,
    .stButton > button[kind="primary"]:focus *,
    .stButton > button[kind="primary"]:active *,
    [data-testid="stFormSubmitButton"] > button:hover *,
    [data-testid="stFormSubmitButton"] > button:focus *,
    [data-testid="stFormSubmitButton"] > button:active * {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    .stButton > button:disabled,
    [data-testid="stFormSubmitButton"] > button:disabled {
        opacity: 0.65 !important;
        cursor: not-allowed !important;
        background-color: #94a3b8 !important;
        color: #ffffff !important;
        border-color: #64748b !important;
        box-shadow: none !important;
        transform: none !important;
    }

    /* ===== Form Inputs & Controls ===== */
    .stTextInput input, .stTextArea textarea, .stSelectbox select, .stNumberInput input {
        font-family: 'Inter', sans-serif !important;
        border-radius: var(--radius-sm) !important;
        border: 1.5px solid #cbd5e1 !important;
        color: #0f172a !important;
        background-color: #ffffff !important;
        font-size: 0.95rem !important;
        padding: 0.6rem 0.8rem !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }

    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox select:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3.5px rgba(37, 99, 235, 0.2) !important;
        outline: none !important;
    }

    .stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label {
        font-weight: 700 !important;
        color: #0f172a !important;
        font-size: 0.9rem !important;
        margin-bottom: 0.25rem !important;
    }

    /* ===== Metric Cards ===== */
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: var(--radius-md) !important;
        padding: 1.15rem 1.35rem !important;
        box-shadow: var(--shadow-sm) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    [data-testid="stMetric"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 20px -4px rgba(37, 99, 235, 0.12) !important;
        border-color: #3b82f6 !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.85rem !important;
        font-weight: 800 !important;
        color: #0f172a !important;
        font-family: 'Inter', sans-serif !important;
        letter-spacing: -0.03em !important;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        color: #475569 !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }

    /* ===== Content Cards & Containers ===== */
    div[data-testid="stVerticalBlock"] > div[style*="border"],
    [data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: var(--radius-md) !important;
        box-shadow: var(--shadow-sm) !important;
        padding: 1.35rem !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {
        box-shadow: var(--shadow-md) !important;
        border-color: #cbd5e1 !important;
    }

    /* ===== Premium Data Tables ===== */
    [data-testid="stDataFrame"], .stTable table {
        border: 1px solid #e2e8f0 !important;
        border-radius: var(--radius-sm) !important;
        overflow: hidden !important;
    }

    .stTable th {
        background-color: #f1f5f9 !important;
        color: #0f172a !important;
        font-weight: 700 !important;
        border-bottom: 2px solid #e2e8f0 !important;
        padding: 0.75rem 1rem !important;
    }

    .stTable td {
        border-bottom: 1px solid #e2e8f0 !important;
        border-right: 1px solid #f1f5f9 !important;
        padding: 0.65rem 1rem !important;
        color: #334155 !important;
    }

    .stTable tr:hover td {
        background-color: #f8fafc !important;
    }

    /* ===== Hero Banner ===== */
    .hero-banner {
        background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 50%, #4f46e5 100%);
        border-radius: var(--radius-lg);
        padding: 2.25rem 2.75rem;
        margin-bottom: 1.75rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.25);
    }

    .hero-banner::before {
        content: '';
        position: absolute;
        top: -40%;
        right: -5%;
        width: 260px;
        height: 260px;
        background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
        border-radius: 50%;
    }

    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        color: #ffffff !important;
        margin-bottom: 0.35rem;
        position: relative;
        z-index: 1;
        letter-spacing: -0.03em;
    }

    .hero-subtitle {
        color: rgba(255, 255, 255, 0.9) !important;
        font-size: 1rem;
        font-weight: 400;
        position: relative;
        z-index: 1;
        line-height: 1.5;
    }

    /* ===== Badges ===== */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 0.25em 0.75em;
        font-size: 0.75rem;
        font-weight: 700;
        border-radius: 999px;
        letter-spacing: 0.02em;
    }
    .badge-active { background: rgba(5, 150, 105, 0.12); color: #047857; }
    .badge-inactive { background: #f1f5f9; color: #64748b; }
    .badge-primary { background: rgba(37, 99, 235, 0.12); color: #1d4ed8; }
    .badge-warning { background: rgba(217, 119, 6, 0.12); color: #b45309; }
    .badge-danger { background: rgba(220, 38, 38, 0.12); color: #b91c1c; }

    /* ===== Empty State ===== */
    .empty-state-card {
        text-align: center;
        padding: 3.5rem 2rem;
        border-radius: var(--radius-lg);
        background: #ffffff;
        border: 2px dashed #cbd5e1;
        margin: 1.5rem 0;
        box-shadow: var(--shadow-sm);
    }
    .empty-state-card h1 { font-size: 3.2rem; margin-bottom: 0.5rem; }
    .empty-state-card h2 { color: #0f172a !important; margin-top: 0.5rem; font-size: 1.3rem; font-weight: 700; }
    .empty-state-card p { color: #475569; font-size: 0.95rem; max-width: 440px; margin: 0.5rem auto 1.5rem; line-height: 1.6; }

    /* ===== Sidebar Branding ===== */
    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.5rem 0.25rem;
        margin-bottom: 0.75rem;
    }
    .sidebar-brand-icon {
        width: 42px;
        height: 42px;
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        border-radius: var(--radius-sm);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.3rem;
        color: #ffffff;
        font-weight: 800;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.45);
    }
    .sidebar-brand-text {
        font-size: 1.1rem;
        font-weight: 800;
        color: #ffffff !important;
        letter-spacing: -0.025em;
    }
    .sidebar-brand-sub {
        font-size: 0.74rem;
        color: #ffffff !important;
        font-weight: 500;
        opacity: 0.85;
    }

    /* ===== Commercial SaaS Footer ===== */
    .saas-footer {
        text-align: center;
        color: #64748b;
        font-size: 0.85rem;
        padding: 3rem 0 1.5rem 0;
        margin-top: 2rem;
        border-top: 1px solid #e2e8f0;
    }
    .saas-footer-brand {
        font-weight: 800;
        color: #0f172a;
    }
    .saas-footer-links {
        margin-top: 0.5rem;
        display: flex;
        justify-content: center;
        gap: 1.5rem;
        font-size: 0.82rem;
        color: #475569;
    }

    /* ===== Sidebar Collapse Button Fix ===== */
    button[data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"] {
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 9999 !important;
        position: fixed !important;
    }

    button[data-testid="stSidebarCollapseButton"] svg,
    [data-testid="collapsedControl"] svg {
        fill: #0f172a !important;
        stroke: #0f172a !important;
    }

    [data-testid="collapsedControl"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
        left: 0.5rem !important;
        top: 0.5rem !important;
    }
    </style>
    """, unsafe_allow_html=True)


def render_hero(title, subtitle, icon=None):
    """Renders a hero banner across all pages."""
    display_title = f"{icon} {title}" if icon else title
    st.markdown(f"""
    <div class="hero-banner">
        <div class="hero-title">{display_title}</div>
        <div class="hero-subtitle">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def render_footer(app_name, version, year):
    """Renders a commercial SaaS footer."""
    st.markdown(f"""
    <div class="saas-footer">
        <div><span class="saas-footer-brand">{app_name}</span> · Version {version}</div>
        <div class="saas-footer-links">
            <span>Powered by AI & Supabase</span>
            <span>·</span>
            <span>&copy; {year} All rights reserved</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_empty_state(icon, title, description, button_label=None, button_key=None):
    """Renders an empty state component with option for action."""
    st.markdown(f"""
    <div class="empty-state-card">
        <h1>{icon}</h1>
        <h2>{title}</h2>
        <p>{description}</p>
    </div>
    """, unsafe_allow_html=True)


def render_badge(text, variant="primary"):
    """Returns HTML for a styled badge."""
    return f'<span class="badge badge-{variant}">{text}</span>'


def render_sidebar_brand():
    """Renders the logo in the sidebar."""
    st.markdown("""
    <div class="sidebar-brand">
        <div class="sidebar-brand-icon">H</div>
        <div>
            <div class="sidebar-brand-text">AI Habit Tracker</div>
            <div class="sidebar-brand-sub">Production SaaS</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
