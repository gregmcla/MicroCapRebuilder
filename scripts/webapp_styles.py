#!/usr/bin/env python3
"""
Design System for GScott Dashboard.

Implements the design consultant's vision:
- Deep navy (#0A1628) + soft teal (#4FD1C5) palette
- Inter + Fraunces typography
- F-pattern layout with floating command bar
- Warm, personality-driven aesthetic

Usage:
    from webapp_styles import STYLES, inject_styles

    inject_styles()  # Call once at start of webapp
"""

# ─── Color Palette ────────────────────────────────────────────────────────────
COLORS = {
    # Backgrounds
    "bg_primary": "#0A1628",
    "bg_card": "#111D2E",
    "bg_hover": "#1A2744",
    "bg_input": "#0D1B2A",

    # Accents
    "accent_teal": "#4FD1C5",
    "accent_teal_dark": "#38B2AC",
    "accent_teal_light": "#81E6D9",

    # Semantic
    "success": "#48BB78",
    "success_light": "#68D391",
    "warning": "#ED8936",
    "warning_light": "#F6AD55",
    "danger": "#F56565",
    "danger_light": "#FC8181",

    # Text
    "text_primary": "#F7FAFC",
    "text_secondary": "#A0AEC0",
    "text_muted": "#4A5568",
    "text_accent": "#4FD1C5",

    # Borders
    "border": "rgba(255,255,255,0.05)",
    "border_light": "rgba(255,255,255,0.1)",
    "border_accent": "rgba(79,209,197,0.3)",
}

# ─── Typography ───────────────────────────────────────────────────────────────
FONTS = {
    "display": "'Fraunces', Georgia, serif",
    "body": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
}

# ─── Main CSS Styles ──────────────────────────────────────────────────────────
STYLES = f"""
<style>
/* ═══════════════════════════════════════════════════════════════════════════
   GScott BOT - DESIGN SYSTEM
   Deep Navy + Soft Teal | Warm & Distinctive
   ═══════════════════════════════════════════════════════════════════════════ */

/* ─── Fonts ─────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fraunces:wght@400;500;600;700&display=swap');

/* ─── CSS Vgscottbles ─────────────────────────────────────────────────────── */
:root {{
    /* Colors */
    --bg-primary: {COLORS["bg_primary"]};
    --bg-card: {COLORS["bg_card"]};
    --bg-hover: {COLORS["bg_hover"]};
    --bg-input: {COLORS["bg_input"]};
    --accent: {COLORS["accent_teal"]};
    --accent-dark: {COLORS["accent_teal_dark"]};
    --accent-light: {COLORS["accent_teal_light"]};
    --success: {COLORS["success"]};
    --warning: {COLORS["warning"]};
    --danger: {COLORS["danger"]};
    --text-primary: {COLORS["text_primary"]};
    --text-secondary: {COLORS["text_secondary"]};
    --text-muted: {COLORS["text_muted"]};
    --border: {COLORS["border"]};
    --border-light: {COLORS["border_light"]};

    /* Typography */
    --font-display: {FONTS["display"]};
    --font-body: {FONTS["body"]};

    /* Spacing */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-6: 24px;
    --space-8: 32px;
    --space-12: 48px;

    /* Border Radius */
    --radius-sm: 6px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 24px;
    --radius-full: 999px;

    /* Shadows */
    --shadow-sm: 0 2px 8px rgba(0,0,0,0.15);
    --shadow-md: 0 4px 20px rgba(0,0,0,0.25);
    --shadow-lg: 0 8px 30px rgba(0,0,0,0.35);
    --shadow-glow: 0 0 20px rgba(79,209,197,0.2);
}}

/* ─── Base Styles ───────────────────────────────────────────────────────── */
.stApp {{
    background: var(--bg-primary) !important;
    font-family: var(--font-body) !important;
}}

.stApp > header {{
    background: transparent !important;
}}

/* ─── Top Bar ───────────────────────────────────────────────────────────── */
.gscott-topbar {{
    background: var(--bg-primary);
    border-bottom: 1px solid var(--border);
    padding: var(--space-3) var(--space-6);
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 1000;
}}

.gscott-logo {{
    font-family: var(--font-display);
    font-size: 24px;
    font-weight: 600;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: var(--space-2);
}}

.gscott-logo-icon {{
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 700;
    color: var(--bg-primary);
}}

.status-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    animation: pulse-glow 2s infinite;
}}

.status-dot.live {{
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
}}

.status-dot.paper {{
    background: var(--warning);
    box-shadow: 0 0 8px var(--warning);
}}

@keyframes pulse-glow {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.6; }}
}}

/* ─── Command Zone (Floating Pill Bar) ──────────────────────────────────── */
.command-zone {{
    display: flex;
    justify-content: center;
    padding: var(--space-4) 0;
    position: sticky;
    top: 60px;
    z-index: 999;
    background: linear-gradient(180deg, var(--bg-primary) 0%, transparent 100%);
}}

.command-pill {{
    background: var(--bg-card);
    border-radius: var(--radius-full);
    padding: var(--space-2);
    display: inline-flex;
    gap: var(--space-2);
    box-shadow: var(--shadow-lg);
    border: 1px solid var(--border-light);
}}

.command-btn {{
    padding: var(--space-3) var(--space-6);
    border-radius: var(--radius-full);
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s ease;
    border: none;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.command-btn.primary {{
    background: var(--accent);
    color: var(--bg-primary);
}}

.command-btn.primary:hover {{
    background: var(--accent-light);
    box-shadow: var(--shadow-glow);
}}

.command-btn.secondary {{
    background: transparent;
    color: var(--text-primary);
    border: 1px solid var(--border-light);
}}

.command-btn.secondary:hover {{
    background: var(--bg-hover);
    border-color: var(--accent);
}}

/* ─── Hero Metrics Ribbon ───────────────────────────────────────────────── */
.metrics-ribbon {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-6);
    padding: var(--space-8) var(--space-6);
    background: var(--bg-card);
    border-radius: var(--radius-xl);
    margin: var(--space-6) 0;
    border: 1px solid var(--border);
}}

.metric-hero {{
    text-align: center;
}}

.metric-value {{
    font-size: 40px;
    font-weight: 800;
    color: var(--text-primary);
    font-family: var(--font-body);
    font-vgscottnt-numeric: tabular-nums;
    line-height: 1.1;
}}

.metric-value.positive {{
    color: var(--success);
}}

.metric-value.negative {{
    color: var(--danger);
}}

.metric-label {{
    font-size: 11px;
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-top: var(--space-2);
}}

.metric-sparkline {{
    height: 24px;
    margin-top: var(--space-3);
    opacity: 0.6;
}}

/* ─── Cards ─────────────────────────────────────────────────────────────── */
.gscott-card {{
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    border: 1px solid var(--border);
    margin-bottom: var(--space-4);
}}

.gscott-card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-4);
}}

.gscott-card-title {{
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 500;
    color: var(--text-primary);
}}

.gscott-card-badge {{
    background: var(--accent);
    color: var(--bg-primary);
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-full);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}}

/* ─── Position Cards ────────────────────────────────────────────────────── */
.position-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-4);
}}

.position-card {{
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    border: 1px solid var(--border);
    transition: all 0.2s ease;
}}

.position-card:hover {{
    border-color: var(--border-light);
    box-shadow: var(--shadow-sm);
}}

.position-card.near-stop {{
    border-color: var(--danger);
    animation: pulse-danger 2s infinite;
}}

.position-card.near-target {{
    border-color: var(--success);
    animation: pulse-success 2s infinite;
}}

@keyframes pulse-danger {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(245, 101, 101, 0.4); }}
    50% {{ box-shadow: 0 0 0 8px rgba(245, 101, 101, 0); }}
}}

@keyframes pulse-success {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(72, 187, 120, 0.4); }}
    50% {{ box-shadow: 0 0 0 8px rgba(72, 187, 120, 0); }}
}}

.position-symbol {{
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.01em;
    margin-bottom: var(--space-2);
}}

.position-pnl {{
    font-size: 14px;
    font-weight: 500;
    margin-bottom: var(--space-3);
}}

.position-pnl.positive {{ color: var(--success); }}
.position-pnl.negative {{ color: var(--danger); }}

.position-progress {{
    height: 6px;
    background: var(--bg-hover);
    border-radius: var(--radius-full);
    position: relative;
    overflow: visible;
}}

.position-progress-track {{
    height: 100%;
    border-radius: var(--radius-full);
    background: linear-gradient(90deg, var(--danger) 0%, var(--text-muted) 50%, var(--success) 100%);
    opacity: 0.3;
}}

.position-progress-marker {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--accent);
    border: 2px solid var(--bg-card);
    position: absolute;
    top: -3px;
    transform: translateX(-50%);
    box-shadow: 0 0 8px var(--accent);
}}

.position-labels {{
    display: flex;
    justify-content: space-between;
    margin-top: var(--space-2);
    font-size: 10px;
    color: var(--text-muted);
}}

/* ─── GScott Companion Sidebar ───────────────────────────────────────────── */
.gscott-sidebar {{
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    border: 1px solid var(--border);
    height: fit-content;
}}

.gscott-avatar {{
    width: 80px;
    height: 80px;
    border-radius: 50%;
    margin: 0 auto var(--space-4);
    border: 3px solid var(--accent);
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, var(--accent-dark) 0%, var(--accent) 100%);
    font-size: 32px;
    color: var(--bg-primary);
    font-weight: 700;
    font-family: var(--font-display);
}}

/* Avatar container for SVG avatar */
.gscott-avatar-container {{
    width: 80px;
    height: 80px;
    margin: 0 auto var(--space-4);
    border-radius: 50%;
    overflow: hidden;
    border: 3px solid var(--accent);
    box-shadow: 0 0 20px rgba(79, 209, 197, 0.2);
    animation: avatar-breathe 4s ease-in-out infinite;
}}

.gscott-avatar-container svg {{
    width: 100%;
    height: 100%;
}}

/* Avatar breathing animation - subtle lifelike movement */
@keyframes avatar-breathe {{
    0%, 100% {{
        transform: scale(1);
        box-shadow: 0 0 20px rgba(79, 209, 197, 0.2);
    }}
    50% {{
        transform: scale(1.02);
        box-shadow: 0 0 25px rgba(79, 209, 197, 0.3);
    }}
}}

.gscott-greeting {{
    font-family: var(--font-display);
    font-size: 18px;
    text-align: center;
    color: var(--text-primary);
    margin-bottom: var(--space-4);
    font-style: italic;
    line-height: 1.5;
    padding: 0 var(--space-2);
}}

.gscott-input {{
    background: var(--bg-input);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    color: var(--text-primary);
    width: 100%;
    font-size: 14px;
}}

.gscott-input:focus {{
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(79,209,197,0.1);
}}

.gscott-insights {{
    margin-top: var(--space-6);
}}

.gscott-insights-title {{
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: var(--space-3);
}}

.gscott-insight {{
    padding: var(--space-2) 0;
    font-size: 13px;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border);
}}

.gscott-insight:last-child {{
    border-bottom: none;
}}

/* ─── Typing Indicator ──────────────────────────────────────────────────── */
.typing-indicator {{
    display: flex;
    gap: 4px;
    padding: var(--space-3);
    justify-content: center;
}}

.typing-dot {{
    width: 8px;
    height: 8px;
    background: var(--accent);
    border-radius: 50%;
    animation: typing-bounce 1.4s infinite ease-in-out;
}}

.typing-dot:nth-child(2) {{ animation-delay: 0.2s; }}
.typing-dot:nth-child(3) {{ animation-delay: 0.4s; }}

@keyframes typing-bounce {{
    0%, 80%, 100% {{ transform: translateY(0); }}
    40% {{ transform: translateY(-6px); }}
}}

/* ─── Text Reveal Animation ────────────────────────────────────────────── */
.gscott-response {{
    animation: text-reveal 0.4s ease-out;
}}

@keyframes text-reveal {{
    from {{
        opacity: 0;
        transform: translateY(8px);
    }}
    to {{
        opacity: 1;
        transform: translateY(0);
    }}
}}

/* ─── Quick Action Chips ───────────────────────────────────────────────── */
.quick-chips {{
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: var(--space-3) 0;
}}

.quick-chip {{
    display: inline-block;
    padding: 6px 14px;
    border: 1px solid var(--accent);
    border-radius: var(--radius-full);
    color: var(--accent);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    background: transparent;
}}

.quick-chip:hover {{
    background: rgba(79, 209, 197, 0.15);
    transform: translateY(-1px);
}}

.quick-chip:active {{
    transform: translateY(0);
}}

/* ─── Enhanced Position Card Danger Glow ───────────────────────────────── */
@keyframes pulse-danger-glow {{
    0%, 100% {{
        box-shadow: 0 0 0 0 rgba(245, 101, 101, 0.4),
                    0 0 15px rgba(245, 101, 101, 0.15);
    }}
    50% {{
        box-shadow: 0 0 0 8px rgba(245, 101, 101, 0),
                    0 0 25px rgba(245, 101, 101, 0.08);
    }}
}}

.position-card.critical {{
    animation: pulse-danger-glow 2s infinite;
    border-color: var(--danger) !important;
}}

/* ─── Success Glow for Near-Target Positions ───────────────────────────── */
@keyframes pulse-success-glow {{
    0%, 100% {{
        box-shadow: 0 0 0 0 rgba(72, 187, 120, 0.4),
                    0 0 15px rgba(72, 187, 120, 0.15);
    }}
    50% {{
        box-shadow: 0 0 0 8px rgba(72, 187, 120, 0),
                    0 0 25px rgba(72, 187, 120, 0.08);
    }}
}}

.position-card.winning {{
    animation: pulse-success-glow 2s infinite;
    border-color: var(--success) !important;
}}

/* ─── Strategy Health Card ──────────────────────────────────────────────── */
.health-card {{
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    border: 1px solid var(--border);
}}

.health-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-4);
}}

.health-grade {{
    font-family: var(--font-display);
    font-size: 48px;
    font-weight: 700;
}}

.health-grade.grade-a {{ color: var(--success); }}
.health-grade.grade-b {{ color: #68D391; }}
.health-grade.grade-c {{ color: var(--warning); }}
.health-grade.grade-d {{ color: #F6AD55; }}
.health-grade.grade-f {{ color: var(--danger); }}

.health-component {{
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
}}

.health-label {{
    flex: 0 0 100px;
    font-size: 12px;
    color: var(--text-secondary);
}}

.health-bar {{
    flex: 1;
    height: 8px;
    background: var(--bg-hover);
    border-radius: var(--radius-full);
    overflow: hidden;
}}

.health-fill {{
    height: 100%;
    border-radius: var(--radius-full);
    transition: width 0.5s ease;
}}

.health-fill.good {{ background: var(--success); }}
.health-fill.warn {{ background: var(--warning); }}
.health-fill.bad {{ background: var(--danger); }}

.health-value {{
    flex: 0 0 40px;
    text-align: right;
    font-size: 12px;
    color: var(--text-secondary);
    font-vgscottnt-numeric: tabular-nums;
}}

/* ─── Pivot Analysis ────────────────────────────────────────────────────── */
.pivot-card {{
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    border: 1px solid var(--border);
    margin-top: var(--space-4);
}}

.pivot-gscott {{
    font-family: var(--font-display);
    font-size: 16px;
    font-style: italic;
    color: var(--text-primary);
    padding: var(--space-4);
    background: var(--bg-hover);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-4);
    border-left: 3px solid var(--accent);
}}

.pivot-section {{
    margin-bottom: var(--space-4);
}}

.pivot-section-title {{
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: var(--space-2);
}}

.pivot-item {{
    padding: var(--space-2) var(--space-3);
    font-size: 13px;
    border-radius: var(--radius-sm);
    margin-bottom: var(--space-1);
}}

.pivot-item.working {{
    background: rgba(72, 187, 120, 0.1);
    color: var(--success);
}}

.pivot-item.failing {{
    background: rgba(245, 101, 101, 0.1);
    color: var(--danger);
}}

.pivot-recommendation {{
    background: var(--bg-hover);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    margin-bottom: var(--space-3);
    border: 1px solid var(--border);
}}

.pivot-recommendation.recommended {{
    border-color: var(--accent);
    background: rgba(79, 209, 197, 0.05);
}}

.pivot-rec-name {{
    font-weight: 600;
    color: var(--text-primary);
}}

.pivot-rec-badge {{
    background: var(--accent);
    color: var(--bg-primary);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-size: 10px;
    font-weight: 600;
    margin-left: var(--space-2);
}}

.pivot-urgency {{
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-full);
    font-size: 11px;
    font-weight: 600;
}}

.pivot-urgency.low {{ background: rgba(72, 187, 120, 0.2); color: var(--success); }}
.pivot-urgency.medium {{ background: rgba(237, 137, 54, 0.2); color: var(--warning); }}
.pivot-urgency.high {{ background: rgba(245, 101, 101, 0.2); color: var(--danger); }}

/* ─── Equity Curve ──────────────────────────────────────────────────────── */
.equity-curve-container {{
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    border: 1px solid var(--border);
}}

/* ─── Streamlit Overrides ───────────────────────────────────────────────── */
.stButton > button {{
    background: var(--accent) !important;
    color: var(--bg-primary) !important;
    border: none !important;
    border-radius: var(--radius-full) !important;
    font-weight: 600 !important;
    padding: var(--space-3) var(--space-6) !important;
    transition: all 0.2s ease !important;
}}

.stButton > button:hover {{
    background: var(--accent-light) !important;
    box-shadow: var(--shadow-glow) !important;
}}

.stButton > button[kind="secondary"] {{
    background: transparent !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-light) !important;
}}

.stTextInput > div > div > input {{
    background: var(--bg-input) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
}}

.stTextInput > div > div > input:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(79,209,197,0.1) !important;
}}

.stSelectbox > div > div {{
    background: var(--bg-input) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius-md) !important;
}}

.stDataFrame {{
    background: var(--bg-card) !important;
    border-radius: var(--radius-md) !important;
}}

/* ─── Hide Streamlit Branding ───────────────────────────────────────────── */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
.stDeployButton {{ display: none; }}

/* ─── Section Headers ───────────────────────────────────────────────────── */
.section-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: var(--space-8) 0 var(--space-4);
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--border);
}}

.section-title {{
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 500;
    color: var(--text-primary);
    letter-spacing: -0.02em;
}}

/* ─── Responsive ────────────────────────────────────────────────────────── */
@media (max-width: 768px) {{
    .metrics-ribbon {{
        grid-template-columns: repeat(2, 1fr);
    }}

    .metric-value {{
        font-size: 24px;
    }}

    .position-grid {{
        grid-template-columns: 1fr;
    }}

    .command-pill {{
        flex-wrap: wrap;
        justify-content: center;
    }}
}}

/* ═══════════════════════════════════════════════════════════════════════════
   TAB-BASED NAVIGATION SYSTEM
   ═══════════════════════════════════════════════════════════════════════════ */

/* ─── Top Header Bar ────────────────────────────────────────────────────── */
.top-header {{
    position: sticky;
    top: 0;
    z-index: 1000;
    background: var(--bg-primary);
    border-bottom: 1px solid var(--border);
    padding: var(--space-2) var(--space-4);
}}

.header-content {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    max-width: 1400px;
    margin: 0 auto;
}}

.header-logo {{
    display: flex;
    align-items: center;
    gap: var(--space-3);
}}

.logo-icon {{
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 700;
    color: var(--bg-primary);
    font-family: var(--font-display);
}}

.logo-text {{
    font-family: var(--font-display);
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
}}

/* ─── Header Controls ───────────────────────────────────────────────────── */
.header-controls {{
    display: flex;
    align-items: center;
    gap: var(--space-4);
}}

.status-indicator {{
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: 12px;
    color: var(--text-secondary);
}}

.status-indicator .dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    animation: pulse 2s infinite;
}}

.status-indicator .dot.connected {{
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
}}

.status-indicator .dot.disconnected {{
    background: var(--danger);
}}

.mode-toggle {{
    display: flex;
    background: var(--bg-card);
    border-radius: var(--radius-full);
    padding: 3px;
}}

.mode-btn {{
    padding: 6px 14px;
    border-radius: var(--radius-full);
    font-size: 11px;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: all 0.2s ease;
}}

.mode-btn.active {{
    background: var(--accent);
    color: var(--bg-primary);
}}

.mode-btn:not(.active) {{
    background: transparent;
    color: var(--text-secondary);
}}

.emergency-btn {{
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(245,101,101,0.1);
    border: 1px solid rgba(245,101,101,0.3);
    color: var(--danger);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
    font-size: 14px;
}}

.emergency-btn:hover {{
    background: rgba(245,101,101,0.2);
    border-color: var(--danger);
}}

/* ─── Compact Metrics Strip ─────────────────────────────────────────────── */
.metrics-strip {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
    padding: var(--space-2) var(--space-4);
    background: var(--bg-card);
    border-bottom: 1px solid var(--border);
    height: 50px;
}}

.strip-metric {{
    display: flex;
    align-items: center;
    gap: var(--space-2);
}}

.strip-metric-value {{
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
    font-vgscottnt-numeric: tabular-nums;
}}

.strip-metric-value.positive {{ color: var(--success); }}
.strip-metric-value.negative {{ color: var(--danger); }}

.strip-metric-label {{
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.strip-divider {{
    width: 1px;
    height: 24px;
    background: var(--border-light);
}}

.regime-badge {{
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 4px 10px;
    border-radius: var(--radius-full);
    font-size: 11px;
    font-weight: 600;
}}

.regime-badge.bull {{
    background: rgba(72,187,120,0.15);
    color: var(--success);
}}

.regime-badge.bear {{
    background: rgba(245,101,101,0.15);
    color: var(--danger);
}}

.regime-badge.sideways {{
    background: rgba(237,137,54,0.15);
    color: var(--warning);
}}

/* ─── Main Layout with Persistent Sidebar ───────────────────────────────── */
.app-layout {{
    display: flex;
    min-height: calc(100vh - 110px);
}}

.main-content {{
    flex: 1;
    padding: var(--space-6);
    max-width: 1100px;
    margin: 0 auto;
    transition: margin-right 0.3s ease;
}}

.main-content.sidebar-open {{
    margin-right: 320px;
}}

/* ─── Collapsible GScott Sidebar ─────────────────────────────────────────── */
.gscott-panel {{
    position: fixed;
    right: 0;
    top: 110px;
    width: 300px;
    height: calc(100vh - 110px);
    background: var(--bg-card);
    border-left: 1px solid var(--border);
    padding: var(--space-4);
    overflow-y: auto;
    transition: transform 0.3s ease, width 0.3s ease;
    z-index: 900;
}}

.gscott-panel.collapsed {{
    width: 60px;
    padding: var(--space-2);
}}

.collapse-btn {{
    position: absolute;
    left: -12px;
    top: 50%;
    transform: translateY(-50%);
    width: 24px;
    height: 48px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px 0 0 8px;
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
}}

.collapse-btn:hover {{
    color: var(--accent);
}}

.panel-content {{
    opacity: 1;
    transition: opacity 0.2s ease;
}}

.gscott-panel.collapsed .panel-content {{
    opacity: 0;
    pointer-events: none;
}}

.collapsed-avatar {{
    display: none;
    width: 44px;
    height: 44px;
    margin: var(--space-2) auto;
    cursor: pointer;
}}

.gscott-panel.collapsed .collapsed-avatar {{
    display: block;
}}

/* ─── Alert Cards ───────────────────────────────────────────────────────── */
.alert-card {{
    background: rgba(237,137,54,0.1);
    border: 1px solid rgba(237,137,54,0.3);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    margin-bottom: var(--space-3);
    display: flex;
    align-items: center;
    gap: var(--space-3);
}}

.alert-card.danger {{
    background: rgba(245,101,101,0.1);
    border-color: rgba(245,101,101,0.3);
}}

.alert-card.success {{
    background: rgba(72,187,120,0.1);
    border-color: rgba(72,187,120,0.3);
}}

.alert-icon {{
    font-size: 18px;
}}

.alert-text {{
    flex: 1;
    font-size: 14px;
    color: var(--text-primary);
}}

.alert-action {{
    font-size: 12px;
    color: var(--accent);
    cursor: pointer;
}}

/* ─── View All Link ─────────────────────────────────────────────────────── */
.view-all-link {{
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-size: 13px;
    color: var(--accent);
    cursor: pointer;
    transition: gap 0.2s ease;
}}

.view-all-link:hover {{
    gap: var(--space-2);
}}

/* ─── Modal Overlay ─────────────────────────────────────────────────────── */
.modal-overlay {{
    position: fixed;
    inset: 0;
    background: rgba(10,22,40,0.9);
    backdrop-filter: blur(4px);
    z-index: 2000;
    display: flex;
    align-items: center;
    justify-content: center;
}}

.modal-content {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    max-width: 480px;
    width: 90%;
}}

.modal-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-4);
}}

.modal-title {{
    font-family: var(--font-display);
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
}}

.modal-close {{
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: 20px;
    cursor: pointer;
}}

/* ─── Contextual Action Buttons ─────────────────────────────────────────── */
.action-bar {{
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
}}

.action-btn {{
    padding: 8px 16px;
    border-radius: var(--radius-md);
    font-size: 13px;
    font-weight: 500;
    border: 1px solid var(--border);
    background: var(--bg-card);
    color: var(--text-primary);
    cursor: pointer;
    transition: all 0.2s ease;
}}

.action-btn:hover {{
    border-color: var(--accent);
    background: rgba(79,209,197,0.1);
}}

.action-btn.primary {{
    background: var(--accent);
    color: var(--bg-primary);
    border-color: var(--accent);
}}

.action-btn.primary:hover {{
    background: var(--accent-light);
}}

/* ─── Compact Equity Curve ──────────────────────────────────────────────── */
.compact-chart {{
    height: 200px;
    background: var(--bg-card);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    padding: var(--space-3);
}}

/* ─── Filter/Sort Controls ──────────────────────────────────────────────── */
.filter-bar {{
    display: flex;
    align-items: center;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
    padding: var(--space-3);
    background: var(--bg-card);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
}}

.filter-group {{
    display: flex;
    align-items: center;
    gap: var(--space-2);
}}

.filter-label {{
    font-size: 12px;
    color: var(--text-muted);
}}

/* ─── Empty State ───────────────────────────────────────────────────────── */
.empty-state {{
    text-align: center;
    padding: var(--space-8);
    color: var(--text-secondary);
}}

.empty-state-icon {{
    font-size: 48px;
    opacity: 0.3;
    margin-bottom: var(--space-4);
}}

.empty-state-text {{
    font-size: 16px;
}}
</style>
"""


def inject_styles() -> str:
    """Return the CSS styles to inject into Streamlit."""
    return STYLES


def get_color(name: str) -> str:
    """Get a color from the palette."""
    return COLORS.get(name, "#FFFFFF")


def get_font(name: str) -> str:
    """Get a font from the typography system."""
    return FONTS.get(name, "sans-serif")


# ─── Component Helpers ────────────────────────────────────────────────────────

def status_dot_html(is_live: bool = True) -> str:
    """Generate HTML for status indicator dot."""
    status = "live" if is_live else "paper"
    return f'<span class="status-dot {status}"></span>'


def metric_html(value: str, label: str, is_positive: bool = None, sparkline: str = "") -> str:
    """Generate HTML for a hero metric."""
    value_class = ""
    if is_positive is True:
        value_class = "positive"
    elif is_positive is False:
        value_class = "negative"

    html = f'<div class="metric-hero">'
    html += f'<div class="metric-value {value_class}">{value}</div>'
    html += f'<div class="metric-label">{label}</div>'
    if sparkline:
        html += f'<div class="metric-sparkline">{sparkline}</div>'
    html += '</div>'
    return html


def position_card_html(
    symbol: str,
    pnl: float,
    pnl_pct: float,
    progress_pct: float,
    stop_price: float,
    target_price: float,
    current_price: float,
    near_stop: bool = False,
    near_target: bool = False
) -> str:
    """Generate HTML for a position card."""
    pnl_class = "positive" if pnl >= 0 else "negative"
    pnl_sign = "+" if pnl >= 0 else ""
    card_class = "near-stop" if near_stop else ("near-target" if near_target else "")

    html = f'<div class="position-card {card_class}">'
    html += f'<div class="position-symbol">{symbol}</div>'
    html += f'<div class="position-pnl {pnl_class}">{pnl_sign}${abs(pnl):,.2f} ({pnl_sign}{pnl_pct:.1f}%)</div>'
    html += '<div class="position-progress">'
    html += '<div class="position-progress-track"></div>'
    html += f'<div class="position-progress-marker" style="left: {min(100, max(0, progress_pct))}%"></div>'
    html += '</div>'
    html += '<div class="position-labels">'
    html += f'<span>Stop ${stop_price:.2f}</span>'
    html += f'<span>${current_price:.2f}</span>'
    html += f'<span>Target ${target_price:.2f}</span>'
    html += '</div>'
    html += '</div>'
    return html


def typing_indicator_html() -> str:
    """Generate HTML for typing indicator."""
    return '''
    <div class="typing-indicator">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
    </div>
    '''


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("GScott Design System")
    print("=" * 50)
    print("\nColor Palette:")
    for name, color in COLORS.items():
        print(f"  {name}: {color}")

    print("\nTypography:")
    for name, font in FONTS.items():
        print(f"  {name}: {font}")

    print("\nCSS Length:", len(STYLES), "characters")
