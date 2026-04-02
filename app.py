import pandas as pd
import plotly.graph_objects
import streamlit as st
from plotly.subplots import make_subplots
from datetime import datetime

from backtest import backtest_ema_strategy
from indicators import calculate_indicators
from utils import (
    calculate_max_drawdown,
    filter_levels,
    load_data,
    load_watchlist,
    save_watchlist,
    load_user_settings,
    save_user_settings,
    load_trade_journal_notes,
    save_trade_journal_notes
)

CHART_BG = "rgba(5, 8, 18, 0.85)"   # leicht heller als Hintergrund
PLOT_BG = "rgba(5, 8, 18, 0.55)"    # innerer Bereich

GRID_COLOR = "rgba(120, 180, 255, 0.08)"
TEXT_COLOR = "#cfd8ff"

invalid_combo = False

# =========================
# DEFAULT SESSION STATE
# =========================

if "period" not in st.session_state:
    st.session_state.period = "6mo"

if "interval" not in st.session_state:
    st.session_state.interval = "1d"

if "chart_theme" not in st.session_state:
    st.session_state.chart_theme = "Dark"

if "fee_percent" not in st.session_state:
    st.session_state.fee_percent = 0.1

if "stop_loss_percent" not in st.session_state:
    st.session_state.stop_loss_percent = 2.0

if "take_profit_percent" not in st.session_state:
    st.session_state.take_profit_percent = 4.0

if "trailing_stop_percent" not in st.session_state:
    st.session_state.trailing_stop_percent = 1.5

if "use_rsi_filter" not in st.session_state:
    st.session_state.use_rsi_filter = False

if "rsi_min" not in st.session_state:
    st.session_state.rsi_min = 30.0

if "rsi_max" not in st.session_state:
    st.session_state.rsi_max = 70.0

if "use_ema200_filter" not in st.session_state:
    st.session_state.use_ema200_filter = False

if "symbol_mode" not in st.session_state:
    st.session_state.symbol_mode = "Watchlist"

if "ticker" not in st.session_state:
    st.session_state.ticker = "TSLA"

if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["TSLA", "AAPL", "NVDA"]

if "compare_input" not in st.session_state:
    st.session_state.compare_input = "TSLA, AAPL, NVDA"

if "show_onboarding" not in st.session_state:
    st.session_state.show_onboarding = True

if "paper_trade_idea" not in st.session_state:
    st.session_state.paper_trade_idea = None

if "trade_idea_prefill_sl" not in st.session_state:
    st.session_state.trade_idea_prefill_sl = None

if "trade_idea_prefill_tp" not in st.session_state:
    st.session_state.trade_idea_prefill_tp = None

if "paper_trade_mode_v2" not in st.session_state:
    st.session_state.paper_trade_mode_v2 = "Stückzahl"

if "paper_trade_qty_v2" not in st.session_state:
    st.session_state.paper_trade_qty_v2 = 1.0

if "paper_trade_amount_v2" not in st.session_state:
    st.session_state.paper_trade_amount_v2 = 1000.0

if "journal_symbol_filter" not in st.session_state:
    st.session_state.journal_symbol_filter = "Alle"

if "journal_result_filter" not in st.session_state:
    st.session_state.journal_result_filter = "Alle"

if "trade_journal_notes" not in st.session_state:
    st.session_state.trade_journal_notes = load_trade_journal_notes()

period = st.session_state.period
interval = st.session_state.interval
fee_percent = st.session_state.fee_percent
stop_loss_percent = st.session_state.stop_loss_percent
take_profit_percent = st.session_state.take_profit_percent
use_rsi_filter = st.session_state.use_rsi_filter
rsi_min = st.session_state.rsi_min
rsi_max = st.session_state.rsi_max
use_ema200_filter = st.session_state.use_ema200_filter

def parse_float_list(input_text):
    values = []
    for item in input_text.split(","):
        item = item.strip()
        if item:
            try:
                values.append(float(item))
            except ValueError:
                pass
    return values


def parse_rsi_ranges(input_text):
    ranges = []
    for item in input_text.split(","):
        item = item.strip()
        if "-" in item:
            parts = item.split("-")
            if len(parts) == 2:
                try:
                    rsi_min_val = float(parts[0].strip())
                    rsi_max_val = float(parts[1].strip())
                    if rsi_min_val <= rsi_max_val:
                        ranges.append((rsi_min_val, rsi_max_val))
                except ValueError:
                    pass
    return ranges

PRESETS = {
    "Daytrading": {
        "period": "5d",
        "interval": "15m",
        "fee_percent": 0.1,
        "stop_loss_percent": 2.0,
        "take_profit_percent": 4.0,
        "use_rsi_filter": True,
        "rsi_min": 45.0,
        "rsi_max": 70.0,
        "use_ema200_filter": False,
        "show_trade_markers": True,
        "show_ema": True,
        "show_fibonacci": False,
        "show_support_resistance": True,
        "show_volume": True,
        "chart_theme": "Dark",
    },
    "Swing Trading": {
        "period": "6mo",
        "interval": "1d",
        "fee_percent": 0.1,
        "stop_loss_percent": 5.0,
        "take_profit_percent": 12.0,
        "use_rsi_filter": True,
        "rsi_min": 40.0,
        "rsi_max": 70.0,
        "use_ema200_filter": True,
        "show_trade_markers": True,
        "show_ema": True,
        "show_fibonacci": True,
        "show_support_resistance": True,
        "show_volume": True,
        "chart_theme": "Dark",
    },
    "Conservative": {
        "period": "1y",
        "interval": "1d",
        "fee_percent": 0.1,
        "stop_loss_percent": 4.0,
        "take_profit_percent": 8.0,
        "use_rsi_filter": True,
        "rsi_min": 45.0,
        "rsi_max": 65.0,
        "use_ema200_filter": True,
        "show_trade_markers": True,
        "show_ema": True,
        "show_fibonacci": True,
        "show_support_resistance": True,
        "show_volume": True,
        "chart_theme": "Light",
    },
    "Aggressive": {
        "period": "3mo",
        "interval": "1h",
        "fee_percent": 0.1,
        "stop_loss_percent": 7.0,
        "take_profit_percent": 15.0,
        "use_rsi_filter": True,
        "rsi_min": 35.0,
        "rsi_max": 75.0,
        "use_ema200_filter": False,
        "show_trade_markers": True,
        "show_ema": True,
        "show_fibonacci": True,
        "show_support_resistance": True,
        "show_volume": True,
        "chart_theme": "Dark",
    },
}

st.markdown("""
<style>
/* Gesamtfläche etwas cleaner */
.main .block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1450px;
}

/* Karten / Container kantiger */
div[data-testid="stMetric"],
div[data-testid="stDataFrame"],
div[data-testid="stExpander"],
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stAlert"]) {
    border-radius: 6px !important;
}

/* Buttons kantiger + technischer */
.stButton > button {
    border-radius: 6px !important;
    border: 1px solid rgba(120, 180, 255, 0.35) !important;
    padding: 0.45rem 0.9rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em;
}

/* Eingabefelder kantiger */
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div {
    border-radius: 6px !important;
}

/* Tabs etwas moderner */
button[data-baseweb="tab"] {
    border-radius: 6px 6px 0 0 !important;
    font-weight: 600 !important;
}

/* Expander */
details {
    border-radius: 6px !important;
    border: 1px solid rgba(120, 180, 255, 0.18);
    padding: 0.2rem 0.4rem;
}

/* Horizontale Linien dezenter */
hr {
    border-top: 1px solid rgba(120, 180, 255, 0.15);
}

/* Kleine Section-Box für Überschriften */
.em-section {
    border: 1px solid rgba(120, 180, 255, 0.20);
    border-radius: 6px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.8rem;
    background: rgba(120, 180, 255, 0.04);
}

/* Subtle futuristic label */
.em-kicker {
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    opacity: 0.75;
    margin-bottom: 0.2rem;
}
            
.em-card {
    border: 1px solid rgba(120, 180, 255, 0.20);
    border-radius: 6px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.6rem;
    background: rgba(120, 180, 255, 0.04);
}

.em-card-title {
    font-weight: 700;
    margin-bottom: 0.25rem;
}

.em-card-sub {
    opacity: 0.8;
    font-size: 0.9rem;
    margin-bottom: 0.15rem;
}
            
.em-card-positive {
    border-left: 4px solid #26a69a;
}

.em-card-negative {
    border-left: 4px solid #ef5350;
}

.em-badge {
    display: inline-block;
    padding: 0.18rem 0.5rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    margin-bottom: 0.35rem;
    border: 1px solid transparent;
}

.em-badge-buy {
    background: rgba(66, 165, 245, 0.16);
    color: #42a5f5;
    border-color: rgba(66, 165, 245, 0.35);
}

.em-badge-sell {
    background: rgba(171, 71, 188, 0.16);
    color: #ab47bc;
    border-color: rgba(171, 71, 188, 0.35);
}

.em-badge-sl {
    background: rgba(239, 83, 80, 0.16);
    color: #ef5350;
    border-color: rgba(239, 83, 80, 0.35);
}

.em-badge-tp {
    background: rgba(38, 166, 154, 0.16);
    color: #26a69a;
    border-color: rgba(38, 166, 154, 0.35);
}

.em-badge-ts {
    background: rgba(255, 152, 0, 0.16);
    color: #ff9800;
    border-color: rgba(255, 152, 0, 0.35);
}
            
/* ===== Global Background / Space Look ===== */
html, body, [data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 20% 20%, rgba(90, 120, 255, 0.10), transparent 22%),
        radial-gradient(circle at 80% 15%, rgba(0, 255, 220, 0.08), transparent 18%),
        radial-gradient(circle at 50% 80%, rgba(120, 60, 255, 0.10), transparent 24%),
        linear-gradient(180deg, #05070d 0%, #070b14 35%, #03050a 100%) !important;
}

/* Hauptbereich dunkler und tiefer */
.main .block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1450px;
}

/* Sidebar Glass / Hologramm */
section[data-testid="stSidebar"] {
    background:
        linear-gradient(180deg, rgba(10, 14, 24, 0.82) 0%, rgba(8, 12, 22, 0.72) 100%) !important;
    backdrop-filter: blur(16px) saturate(130%);
    -webkit-backdrop-filter: blur(16px) saturate(130%);
    border-right: 1px solid rgba(130, 180, 255, 0.15);
    box-shadow: inset -1px 0 0 rgba(255,255,255,0.04);
}

/* Sidebar Inhalt etwas ruhiger */
section[data-testid="stSidebar"] .block-container {
    padding-top: 1rem;
}

/* Große Hero Headline */
.em-hero {
    position: relative;
    border: 1px solid rgba(120, 180, 255, 0.18);
    border-radius: 8px;
    padding: 1.2rem 1.2rem 1rem 1.2rem;
    margin-bottom: 1rem;
    background:
        linear-gradient(180deg, rgba(120, 180, 255, 0.06) 0%, rgba(120, 180, 255, 0.02) 100%);
    overflow: hidden;
}

.em-hero::before {
    content: "";
    position: absolute;
    inset: 0;
    background:
        radial-gradient(circle at top right, rgba(120,180,255,0.14), transparent 30%),
        linear-gradient(90deg, transparent, rgba(255,255,255,0.03), transparent);
    pointer-events: none;
}

.em-hero-kicker {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    opacity: 0.65;
    margin-bottom: 0.25rem;
}

.em-hero-title {
    font-size: 2.6rem;
    line-height: 1;
    font-weight: 800;
    letter-spacing: 0.04em;
    margin-bottom: 0.35rem;
    color: #f3f7ff;
    text-shadow: 0 0 18px rgba(120, 180, 255, 0.12);
}

.em-hero-subtitle {
    font-size: 0.98rem;
    opacity: 0.78;
    max-width: 900px;
}

/* Dezentere Cards */
.em-section,
.em-card {
    background: rgba(120, 180, 255, 0.035);
    border: 1px solid rgba(120, 180, 255, 0.15);
    box-shadow: 0 8px 30px rgba(0,0,0,0.16);
}

/* Metrics etwas cleaner */
div[data-testid="stMetric"] {
    background: rgba(120, 180, 255, 0.03);
    border: 1px solid rgba(120, 180, 255, 0.14);
    border-radius: 8px !important;
    padding: 0.55rem 0.7rem;
}

/* Buttons technischer */
.stButton > button {
    background: linear-gradient(180deg, rgba(22,28,42,0.95), rgba(13,18,30,0.95)) !important;
    color: #e8f1ff !important;
    border-radius: 6px !important;
    border: 1px solid rgba(120, 180, 255, 0.25) !important;
    box-shadow: 0 0 0 1px rgba(255,255,255,0.02) inset;
}

.stButton > button:hover {
    border-color: rgba(120, 180, 255, 0.45) !important;
    box-shadow: 0 0 18px rgba(120, 180, 255, 0.10);
}

/* Inputs moderner */
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div {
    background: rgba(9, 13, 22, 0.82) !important;
    border: 1px solid rgba(120, 180, 255, 0.16) !important;
    border-radius: 6px !important;
}

/* Tabs dezenter und professioneller */
button[data-baseweb="tab"] {
    border-radius: 6px 6px 0 0 !important;
    font-weight: 600 !important;
    opacity: 0.92;
}

/* Horizontale Linien feiner */
hr {
    border-top: 1px solid rgba(120, 180, 255, 0.10);
}

/* Alerts etwas edler */
div[data-testid="stAlert"] {
    border-radius: 8px !important;
    border: 1px solid rgba(120, 180, 255, 0.10);
    background: rgba(120, 180, 255, 0.035);
}

/* Expander ruhiger */
details {
    border-radius: 6px !important;
    border: 1px solid rgba(120, 180, 255, 0.14);
    background: rgba(120, 180, 255, 0.02);
}

/* Datenframes etwas cleaner */
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(120, 180, 255, 0.12);
    border-radius: 8px !important;
    overflow: hidden;
}
            
/* ===== Layout / Spacing Polish ===== */
.main .block-container {
    padding-top: 1rem;
    padding-bottom: 2.2rem;
}

[data-testid="stVerticalBlock"] > div:has(> div .em-subsection-title),
[data-testid="stVerticalBlock"] > div:has(> div .em-panel-title) {
    margin-top: 0.35rem;
}

/* ===== Reusable Section Titles ===== */
.em-subsection-title {
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    margin: 0.25rem 0 0.65rem 0;
    color: #eef4ff;
}

.em-subsection-caption {
    opacity: 0.75;
    font-size: 0.92rem;
    margin: -0.25rem 0 0.8rem 0;
}

/* ===== Cleaner Panels ===== */
.em-panel {
    border: 1px solid rgba(120, 180, 255, 0.14);
    border-radius: 10px;
    padding: 0.95rem 1rem;
    margin-bottom: 0.9rem;
    background: rgba(120, 180, 255, 0.03);
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.14);
}

.em-panel-title {
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
}

.em-panel-sub {
    font-size: 0.92rem;
    opacity: 0.8;
}

/* ===== Card polish ===== */
.em-card {
    border-radius: 10px;
    padding: 0.95rem 1rem;
    margin-bottom: 0.75rem;
    background: rgba(120, 180, 255, 0.035);
    border: 1px solid rgba(120, 180, 255, 0.14);
    box-shadow: 0 8px 22px rgba(0,0,0,0.13);
}

.em-card-title {
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
}

.em-card-sub {
    opacity: 0.84;
    font-size: 0.92rem;
    line-height: 1.42;
}

/* ===== Metrics tighter and more consistent ===== */
div[data-testid="stMetric"] {
    min-height: 102px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

/* ===== Inputs / buttons ===== */
.stButton > button,
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div {
    transition: all 0.16s ease;
}

div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="textarea"] > div:focus-within {
    border-color: rgba(120, 180, 255, 0.34) !important;
    box-shadow: 0 0 0 1px rgba(120, 180, 255, 0.08), 0 0 18px rgba(120, 180, 255, 0.06);
}

.stButton > button {
    min-height: 42px;
}

.stButton > button:hover {
    transform: translateY(-1px);
}

/* ===== Expander polish ===== */
details summary {
    font-weight: 600;
}

/* ===== Dataframe polish ===== */
div[data-testid="stDataFrame"] {
    background: rgba(8, 12, 20, 0.24);
}

/* ===== Sidebar polish ===== */
section[data-testid="stSidebar"] .stButton > button {
    width: 100%;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    letter-spacing: 0.01em;
}

/* ===== Small spacing helper ===== */
.em-gap-sm {
    height: 0.35rem;
}

.em-gap-md {
    height: 0.7rem;
}

.em-gap-lg {
    height: 1rem;
}

.em-chart-container {
    border-radius: 14px;
    padding: 0.6rem 0.6rem 0.3rem 0.6rem;
    margin-bottom: 1rem;

    background: rgba(120, 180, 255, 0.04);
    border: 1px solid rgba(120, 180, 255, 0.16);

    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);

    box-shadow: 0 12px 32px rgba(0,0,0,0.25);
}
            
/* =========================
   Emanacci Final Polish
   ========================= */

:root {
    --em-glass-bg: rgba(120, 180, 255, 0.045);
    --em-glass-border: rgba(120, 180, 255, 0.16);
    --em-glow: 0 14px 36px rgba(0,0,0,0.22);
    --em-text-soft: rgba(235, 242, 255, 0.78);
    --em-text-strong: #eef4ff;
    --em-radius: 14px;
}

/* Main spacing */
.main .block-container {
    padding-top: 1rem;
    padding-bottom: 2.4rem;
    max-width: 1450px;
}

/* Cleaner markdown rhythm */
.element-container {
    margin-bottom: 0.2rem;
}

/* Section hero */
.em-hero {
    border-radius: 18px;
    padding: 1rem 1.15rem;
    margin-bottom: 1rem;
    background:
        linear-gradient(135deg, rgba(120,180,255,0.08), rgba(120,180,255,0.02)),
        rgba(10, 18, 30, 0.34);
    border: 1px solid rgba(120, 180, 255, 0.16);
    box-shadow: 0 14px 38px rgba(0,0,0,0.24);
}

.em-hero-title {
    font-size: 1.18rem;
    font-weight: 800;
    color: var(--em-text-strong);
    margin-bottom: 0.25rem;
}

.em-hero-sub {
    color: var(--em-text-soft);
    font-size: 0.94rem;
    line-height: 1.45;
}

/* Section titles */
.em-section-title {
    font-size: 1.08rem;
    font-weight: 800;
    letter-spacing: 0.01em;
    margin: 0.35rem 0 0.2rem 0;
    color: var(--em-text-strong);
}

.em-section-caption {
    color: var(--em-text-soft);
    font-size: 0.92rem;
    margin: 0 0 0.75rem 0;
}

/* Panels */
.em-panel {
    border: 1px solid var(--em-glass-border);
    border-radius: var(--em-radius);
    padding: 1rem 1rem;
    margin-bottom: 0.9rem;
    background: var(--em-glass-bg);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: var(--em-glow);
}

.em-panel-title {
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
    color: var(--em-text-strong);
}

.em-panel-sub {
    color: var(--em-text-soft);
    font-size: 0.92rem;
    line-height: 1.45;
}

/* Cards */
.em-card {
    border-radius: var(--em-radius);
    padding: 0.95rem 1rem;
    margin-bottom: 0.8rem;
    background: var(--em-glass-bg);
    border: 1px solid var(--em-glass-border);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 10px 28px rgba(0,0,0,0.16);
}

.em-card-title {
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 0.28rem;
    color: var(--em-text-strong);
}

.em-card-sub {
    color: var(--em-text-soft);
    font-size: 0.92rem;
    line-height: 1.45;
}

.em-card-positive {
    border-color: rgba(38, 166, 154, 0.45);
    box-shadow: 0 10px 28px rgba(20, 140, 110, 0.14);
}

.em-card-negative {
    border-color: rgba(239, 83, 80, 0.42);
    box-shadow: 0 10px 28px rgba(170, 40, 50, 0.12);
}

/* Badges */
.em-badge {
    display: inline-block;
    padding: 0.26rem 0.55rem;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
    border: 1px solid rgba(255,255,255,0.08);
}

.em-badge-buy { background: rgba(38,166,154,0.16); color: #8ef0d3; }
.em-badge-sell { background: rgba(239,83,80,0.14); color: #ffb1ac; }
.em-badge-sl { background: rgba(239,83,80,0.14); color: #ffb1ac; }
.em-badge-tp { background: rgba(38,166,154,0.16); color: #8ef0d3; }
.em-badge-ts { background: rgba(171,71,188,0.16); color: #e0b4ff; }

/* Chart container */
.em-chart-container {
    border-radius: 16px;
    padding: 0.65rem 0.65rem 0.3rem 0.65rem;
    margin-bottom: 1rem;
    background: var(--em-glass-bg);
    border: 1px solid var(--em-glass-border);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 14px 34px rgba(0,0,0,0.22);
}

/* Metrics */
div[data-testid="stMetric"] {
    min-height: 102px;
    border-radius: 14px;
    padding: 0.45rem 0.55rem;
    background: rgba(120, 180, 255, 0.025);
}

div[data-testid="stMetricLabel"] {
    font-weight: 600;
}

div[data-testid="stMetricValue"] {
    letter-spacing: -0.01em;
}

/* Inputs / buttons */
.stButton > button {
    min-height: 42px;
    border-radius: 12px;
    border: 1px solid rgba(120, 180, 255, 0.16);
    background: rgba(120,180,255,0.045);
    transition: all 0.16s ease;
}

.stButton > button:hover {
    transform: translateY(-1px);
    border-color: rgba(120, 180, 255, 0.26);
    box-shadow: 0 8px 18px rgba(0,0,0,0.18);
}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div {
    border-radius: 12px !important;
}

div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="textarea"] > div:focus-within {
    border-color: rgba(120, 180, 255, 0.34) !important;
    box-shadow: 0 0 0 1px rgba(120, 180, 255, 0.08), 0 0 18px rgba(120, 180, 255, 0.06);
}

/* Expanders */
details {
    border-radius: 12px;
    overflow: hidden;
}

details summary {
    font-weight: 700;
}

/* Sidebar */
section[data-testid="stSidebar"] .block-container {
    padding-top: 1rem;
}

section[data-testid="stSidebar"] .stButton > button {
    width: 100%;
}

/* Small helpers */
.em-gap-sm { height: 0.35rem; }
.em-gap-md { height: 0.7rem; }
.em-gap-lg { height: 1rem; }
            
/* =========================
   Emanacci Layout System
   ========================= */

.em-center-wrap {
    width: 100%;
}

.em-narrow-wrap {
    max-width: 860px;
    margin: 0 auto 0 auto;
}

.em-medium-wrap {
    max-width: 1120px;
    margin: 0 auto 0 auto;
}

.em-wide-wrap {
    max-width: 1380px;
    margin: 0 auto 0 auto;
}

.em-section-block {
    margin-bottom: 1rem;
}

.em-soft-divider {
    height: 1px;
    margin: 1rem 0 1rem 0;
    background: linear-gradient(
        90deg,
        rgba(120,180,255,0.00),
        rgba(120,180,255,0.16),
        rgba(120,180,255,0.00)
    );
    border-radius: 999px;
}

.em-subgrid-note {
    color: rgba(235, 242, 255, 0.72);
    font-size: 0.89rem;
    margin-top: -0.2rem;
    margin-bottom: 0.55rem;
}

.em-form-card {
    border-radius: 16px;
    padding: 1rem;
    background: rgba(120, 180, 255, 0.035);
    border: 1px solid rgba(120, 180, 255, 0.14);
    box-shadow: 0 12px 28px rgba(0,0,0,0.16);
    margin-bottom: 0.9rem;
}

.streamlit-expanderHeader {
    font-weight: 700;
}
            
/* =========================
   Emanacci Metrics / Card Tweaks
   ========================= */

div[data-testid="stMetricValue"] {
    font-size: 1.35rem !important;
    line-height: 1.15 !important;
    white-space: normal !important;
    overflow-wrap: anywhere !important;
}

div[data-testid="stMetricLabel"] {
    font-size: 0.88rem !important;
}

.em-card-number {
    font-size: 1.08rem;
    font-weight: 700;
    line-height: 1.2;
    word-break: break-word;
}

.em-mini-chart-wrap {
    margin-top: 0.45rem;
    border-top: 1px solid rgba(120, 180, 255, 0.10);
    padding-top: 0.45rem;
}
            
.em-watch-card-shell {
    border-radius: 14px;
    padding: 0.95rem 1rem;
    margin-bottom: 0.8rem;
    background: rgba(120, 180, 255, 0.045);
    border: 1px solid rgba(120, 180, 255, 0.16);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 10px 28px rgba(0,0,0,0.16);
}

.em-watch-card-right {
    padding-left: 0.4rem;
}

.em-watch-card-left .em-card-title {
    margin-bottom: 0.35rem;
}

.em-watch-card-mini-title {
    font-size: 0.78rem;
    color: rgba(235, 242, 255, 0.66);
    margin-bottom: 0.25rem;
}
          
.em-overview-card-shell {
    border-radius: 14px;
    padding: 0.9rem 1rem;
    margin-bottom: 0.8rem;
    background: rgba(120, 180, 255, 0.045);
    border: 1px solid rgba(120, 180, 255, 0.16);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 10px 28px rgba(0,0,0,0.16);
}

.em-overview-card-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: rgba(235, 242, 255, 0.78);
    margin-bottom: 0.18rem;
}

.em-overview-card-value {
    font-size: 1.18rem;
    font-weight: 800;
    color: #eef4ff;
    line-height: 1.2;
    word-break: break-word;
}

.em-overview-card-sub {
    font-size: 0.82rem;
    color: rgba(235, 242, 255, 0.62);
    margin-top: 0.18rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="em-hero">
    <div class="em-hero-kicker">quant · analysis · paper trading</div>
    <div class="em-hero-title">Emanacci</div>
    <div class="em-hero-subtitle">Technische Marktanalyse, Backtesting und virtuelles Trading in einer Oberfläche.</div>
</div>
""", unsafe_allow_html=True)

def calc_stats_for_optimization(trades_df, equity_df):
    if trades_df.empty or equity_df.empty:
        return {
            "Return %": 0,
            "Win Rate %": 0,
            "Avg Trade %": 0,
            "Profit Factor": 0,
            "Max Drawdown %": 0,
            "Trades": 0
        }

    total_return = ((equity_df["Equity"].iloc[-1] / 1000) - 1) * 100
    win_rate = (trades_df["Trade Return After Fees %"] > 0).mean() * 100
    avg_return = trades_df["Trade Return After Fees %"].mean()
    max_dd = calculate_max_drawdown(equity_df)

    wins = trades_df[trades_df["Trade Return After Fees %"] > 0]
    losses = trades_df[trades_df["Trade Return After Fees %"] < 0]

    total_profit = wins["Trade Return After Fees %"].sum() if not wins.empty else 0
    total_loss = abs(losses["Trade Return After Fees %"].sum()) if not losses.empty else 0
    profit_factor = (total_profit / total_loss) if total_loss > 0 else 0

    return {
        "Return %": round(total_return, 2),
        "Win Rate %": round(win_rate, 2),
        "Avg Trade %": round(avg_return, 2),
        "Profit Factor": round(profit_factor, 2),
        "Max Drawdown %": round(max_dd, 2),
        "Trades": len(trades_df)
    }

def update_paper_equity_snapshot():
    total_positions_value = 0.0

    for symbol, pos in st.session_state.paper_positions.items():
        try:
            symbol_data = load_data(symbol, period="5d", interval="1d")

            if not symbol_data.empty and "Close" in symbol_data.columns:
                current_price = float(symbol_data["Close"].iloc[-1])
            else:
                current_price = pos["avg_price"]
        except Exception:
            current_price = pos["avg_price"]

        market_value = pos["quantity"] * current_price
        total_positions_value += market_value

    total_equity = st.session_state.paper_cash + total_positions_value

    st.session_state.paper_equity_history.append({
        "Zeit": datetime.now(),
        "Cash": round(st.session_state.paper_cash, 2),
        "Positionswert": round(total_positions_value, 2),
        "Gesamtwert": round(total_equity, 2)
    })

def process_limit_orders():
    if not st.session_state.paper_open_orders:
        return

    remaining_orders = []

    for order in st.session_state.paper_open_orders:
        symbol = order["Symbol"]

        try:
            order_data = load_data(symbol, period="5d", interval="1d")

            if order_data.empty or "Close" not in order_data.columns:
                remaining_orders.append(order)
                continue

            current_price = float(order_data["Close"].iloc[-1])
            trade_time = order_data.index[-1]
            fee_rate = st.session_state.fee_percent / 100

            order_type = order["Order Type"]
            quantity = int(order["Stück"])
            limit_price = float(order["Limit Price"])

            # LIMIT BUY
            if order_type == "Limit Buy":
                if current_price <= limit_price:
                    gross_cost = current_price * quantity
                    fee_cost = gross_cost * fee_rate
                    total_cost = gross_cost + fee_cost

                    if st.session_state.paper_cash >= total_cost:
                        if symbol not in st.session_state.paper_positions:
                            st.session_state.paper_positions[symbol] = {
                                "quantity": 0,
                                "avg_price": 0.0,
                                "total_cost": 0.0
                            }

                        old_qty = st.session_state.paper_positions[symbol]["quantity"]
                        old_total_cost = st.session_state.paper_positions[symbol]["total_cost"]

                        new_qty = old_qty + quantity
                        new_total_cost = old_total_cost + total_cost
                        new_avg = new_total_cost / new_qty

                        st.session_state.paper_positions[symbol]["quantity"] = new_qty
                        st.session_state.paper_positions[symbol]["avg_price"] = new_avg
                        st.session_state.paper_positions[symbol]["total_cost"] = new_total_cost

                        st.session_state.paper_cash -= total_cost

                        st.session_state.paper_history.append({
                            "Zeit": trade_time,
                            "Typ": "Kauf",
                            "Symbol": symbol,
                            "Stück": quantity,
                            "Preis": round(current_price, 2),
                            "Gebühr": round(fee_cost, 2),
                            "Gesamt": round(total_cost, 2),
                            "Order": "Limit Buy"
                        })

                        update_paper_equity_snapshot()
                    else:
                        remaining_orders.append(order)
                else:
                    remaining_orders.append(order)

            # LIMIT SELL
            elif order_type == "Limit Sell":
                if current_price >= limit_price:
                    if symbol in st.session_state.paper_positions:
                        position = st.session_state.paper_positions[symbol]
                        held_qty = position["quantity"]

                        if held_qty >= quantity:
                            gross_value = current_price * quantity
                            fee_cost = gross_value * fee_rate
                            total_value = gross_value - fee_cost

                            avg_price = position["avg_price"]
                            total_position_cost = position["total_cost"]

                            cost_basis_sold = avg_price * quantity
                            realized_pnl = total_value - cost_basis_sold

                            st.session_state.paper_cash += total_value

                            remaining_qty = held_qty - quantity
                            remaining_total_cost = total_position_cost - cost_basis_sold

                            if remaining_qty > 0:
                                st.session_state.paper_positions[symbol]["quantity"] = remaining_qty
                                st.session_state.paper_positions[symbol]["total_cost"] = remaining_total_cost
                                st.session_state.paper_positions[symbol]["avg_price"] = remaining_total_cost / remaining_qty
                            else:
                                del st.session_state.paper_positions[symbol]

                            st.session_state.paper_history.append({
                                "Zeit": trade_time,
                                "Typ": "Verkauf",
                                "Symbol": symbol,
                                "Stück": quantity,
                                "Preis": round(current_price, 2),
                                "Gebühr": round(fee_cost, 2),
                                "Gesamt": round(total_value, 2),
                                "Realized PnL": round(realized_pnl, 2),
                                "Order": "Limit Sell"
                            })

                            update_paper_equity_snapshot()
                        else:
                            remaining_orders.append(order)
                    else:
                        remaining_orders.append(order)
                else:
                    remaining_orders.append(order)

            # STOP LOSS
            elif order_type == "Stop-Loss":
                if symbol in st.session_state.paper_positions:
                    if current_price <= limit_price:
                        position = st.session_state.paper_positions[symbol]
                        quantity = position["quantity"]

                        gross_value = current_price * quantity
                        fee_cost = gross_value * fee_rate
                        total_value = gross_value - fee_cost

                        total_cost = position["total_cost"]
                        realized_pnl = total_value - total_cost

                        st.session_state.paper_cash += total_value
                        del st.session_state.paper_positions[symbol]

                        st.session_state.paper_history.append({
                            "Zeit": trade_time,
                            "Typ": "Verkauf",
                            "Symbol": symbol,
                            "Stück": quantity,
                            "Preis": round(current_price, 2),
                            "Gebühr": round(fee_cost, 2),
                            "Gesamt": round(total_value, 2),
                            "Realized PnL": round(realized_pnl, 2),
                            "Order": "Stop-Loss"
                        })

                        update_paper_equity_snapshot()
                    else:
                        remaining_orders.append(order)
                else:
                    remaining_orders.append(order)

            # TAKE PROFIT
            elif order_type == "Take-Profit":
                if symbol in st.session_state.paper_positions:
                    if current_price >= limit_price:
                        position = st.session_state.paper_positions[symbol]
                        quantity = position["quantity"]

                        gross_value = current_price * quantity
                        fee_cost = gross_value * fee_rate
                        total_value = gross_value - fee_cost

                        total_cost = position["total_cost"]
                        realized_pnl = total_value - total_cost

                        st.session_state.paper_cash += total_value
                        del st.session_state.paper_positions[symbol]

                        st.session_state.paper_history.append({
                            "Zeit": trade_time,
                            "Typ": "Verkauf",
                            "Symbol": symbol,
                            "Stück": quantity,
                            "Preis": round(current_price, 2),
                            "Gebühr": round(fee_cost, 2),
                            "Gesamt": round(total_value, 2),
                            "Realized PnL": round(realized_pnl, 2),
                            "Order": "Take-Profit"
                        })

                        # OCO: passendes Stop-Loss für dasselbe Symbol löschen
                        remaining_orders = [
                            o for o in remaining_orders
                            if not (
                                o["Symbol"] == symbol
                                and o["Order Type"] == "Stop-Loss"
                            )
                        ]

                        update_paper_equity_snapshot()
                    else:
                        remaining_orders.append(order)
                else:
                    # Keine Position mehr vorhanden -> Order nicht behalten
                    pass

            # TRAILING STOP
            elif order_type == "Trailing Stop":
                if symbol in st.session_state.paper_positions:
                    anchor_price = float(order.get("Anchor Price", current_price))
                    trailing_percent = st.session_state.trailing_stop_percent / 100

                    # Anchor nur nach oben anpassen
                    if current_price > anchor_price:
                        anchor_price = current_price

                    trailing_stop_price = anchor_price * (1 - trailing_percent)

                    # Stop aktualisiert behalten
                    order["Anchor Price"] = anchor_price
                    order["Limit Price"] = trailing_stop_price

                    if current_price <= trailing_stop_price:
                        position = st.session_state.paper_positions[symbol]
                        quantity = position["quantity"]

                        gross_value = current_price * quantity
                        fee_cost = gross_value * fee_rate
                        total_value = gross_value - fee_cost

                        total_cost = position["total_cost"]
                        realized_pnl = total_value - total_cost

                        st.session_state.paper_cash += total_value
                        del st.session_state.paper_positions[symbol]

                        st.session_state.paper_history.append({
                            "Zeit": trade_time,
                            "Typ": "Verkauf",
                            "Symbol": symbol,
                            "Stück": quantity,
                            "Preis": round(current_price, 2),
                            "Gebühr": round(fee_cost, 2),
                            "Gesamt": round(total_value, 2),
                            "Realized PnL": round(realized_pnl, 2),
                            "Order": "Trailing Stop"
                        })

                        update_paper_equity_snapshot()
                    else:
                        remaining_orders.append(order)
                else:
                    pass

        except Exception:
            remaining_orders.append(order)

    st.session_state.paper_open_orders = remaining_orders

def get_latest_price_for_symbol(symbol: str):
    try:
        price_data = load_data(symbol, period="5d", interval="1d")
        if not price_data.empty and "Close" in price_data.columns:
            return float(price_data["Close"].iloc[-1]), price_data.index[-1]
    except Exception:
        pass
    return None, None


def ensure_paper_position(symbol: str):
    if symbol not in st.session_state.paper_positions:
        st.session_state.paper_positions[symbol] = {
            "quantity": 0,
            "avg_price": 0.0,
            "total_cost": 0.0
        }


def calculate_buy_quantity_from_input(
    mode: str,
    current_price: float,
    fee_rate: float,
    quantity_value: int,
    amount_value: float,
    available_cash: float
):
    if current_price <= 0:
        return 0, 0.0, 0.0, 0.0

    if mode == "Stückzahl":
        quantity = int(quantity_value)
    else:
        invest_amount = float(amount_value)
        quantity = int(invest_amount / (current_price * (1 + fee_rate)))

    if quantity < 1:
        return 0, 0.0, 0.0, 0.0

    gross_cost = current_price * quantity
    fee_cost = gross_cost * fee_rate
    total_cost = gross_cost + fee_cost

    if total_cost > available_cash:
        max_quantity = int(available_cash / (current_price * (1 + fee_rate)))
        quantity = max_quantity

        if quantity < 1:
            return 0, 0.0, 0.0, 0.0

        gross_cost = current_price * quantity
        fee_cost = gross_cost * fee_rate
        total_cost = gross_cost + fee_cost

    return quantity, gross_cost, fee_cost, total_cost


def calculate_sell_quantity_from_input(
    mode: str,
    current_price: float,
    quantity_value: int,
    amount_value: float,
    held_qty: int
):
    if current_price <= 0 or held_qty <= 0:
        return 0

    if mode == "Stückzahl":
        quantity = int(quantity_value)
    else:
        sell_amount = float(amount_value)
        quantity = int(sell_amount / current_price)

    if quantity < 1:
        return 0

    return min(quantity, held_qty)


def execute_market_buy(symbol: str, quantity: int, current_price: float, trade_time, fee_rate: float):
    if quantity < 1:
        return False, "Menge zu klein."

    gross_cost = current_price * quantity
    fee_cost = gross_cost * fee_rate
    total_cost = gross_cost + fee_cost

    if st.session_state.paper_cash < total_cost:
        return False, "Nicht genug Spielgeld verfügbar."

    ensure_paper_position(symbol)

    old_qty = st.session_state.paper_positions[symbol]["quantity"]
    old_total_cost = st.session_state.paper_positions[symbol]["total_cost"]

    new_qty = old_qty + quantity
    new_total_cost = old_total_cost + total_cost
    new_avg = new_total_cost / new_qty

    st.session_state.paper_positions[symbol]["quantity"] = new_qty
    st.session_state.paper_positions[symbol]["avg_price"] = new_avg
    st.session_state.paper_positions[symbol]["total_cost"] = new_total_cost

    st.session_state.paper_cash -= total_cost

    st.session_state.paper_history.append({
        "Zeit": trade_time,
        "Typ": "Kauf",
        "Symbol": symbol,
        "Stück": quantity,
        "Preis": round(current_price, 2),
        "Gebühr": round(fee_cost, 2),
        "Gesamt": round(total_cost, 2),
        "Order": "Market Buy"
    })

    update_paper_equity_snapshot()
    return True, f"{quantity} Stück {symbol} wurden virtuell gekauft."


def execute_market_sell(symbol: str, quantity: int, current_price: float, trade_time, fee_rate: float):
    if symbol not in st.session_state.paper_positions:
        return False, "Keine Position vorhanden."

    position = st.session_state.paper_positions[symbol]
    held_qty = position["quantity"]

    if quantity < 1:
        return False, "Menge zu klein."

    if held_qty + 1e-9 < quantity:
        return False, "Nicht genug Stück vorhanden."

    gross_value = current_price * quantity
    fee_cost = gross_value * fee_rate
    total_value = gross_value - fee_cost

    avg_price = position["avg_price"]
    total_position_cost = position["total_cost"]

    cost_basis_sold = avg_price * quantity
    realized_pnl = total_value - cost_basis_sold

    st.session_state.paper_cash += total_value

    remaining_qty = held_qty - quantity
    remaining_total_cost = total_position_cost - cost_basis_sold

    if remaining_qty > 0:
        st.session_state.paper_positions[symbol]["quantity"] = remaining_qty
        st.session_state.paper_positions[symbol]["total_cost"] = remaining_total_cost
        st.session_state.paper_positions[symbol]["avg_price"] = remaining_total_cost / remaining_qty
    else:
        del st.session_state.paper_positions[symbol]

    st.session_state.paper_history.append({
        "Zeit": trade_time,
        "Typ": "Verkauf",
        "Symbol": symbol,
        "Stück": quantity,
        "Preis": round(current_price, 2),
        "Gebühr": round(fee_cost, 2),
        "Gesamt": round(total_value, 2),
        "Realized PnL": round(realized_pnl, 2),
        "Order": "Market Sell"
    })

    update_paper_equity_snapshot()
    return True, f"{quantity} Stück {symbol} wurden virtuell verkauft."

def build_paper_positions_snapshot():
    position_rows = []
    total_positions_value = 0.0

    for symbol, pos in st.session_state.paper_positions.items():
        quantity = int(pos.get("quantity", 0))
        avg_price = float(pos.get("avg_price", 0.0))
        total_cost = float(pos.get("total_cost", quantity * avg_price))

        if quantity <= 0:
            continue

        symbol_data = load_data(symbol, period="5d", interval="1d")

        if symbol_data.empty or "Close" not in symbol_data.columns:
            current_price_symbol = avg_price
            current_time_symbol = datetime.now()
        else:
            current_price_symbol = float(symbol_data["Close"].iloc[-1])
            current_time_symbol = symbol_data.index[-1]

        market_value = quantity * current_price_symbol
        open_pnl = market_value - total_cost
        open_pnl_pct = (open_pnl / total_cost * 100) if total_cost > 0 else 0

        total_positions_value += market_value

        position_rows.append({
            "Symbol": symbol,
            "Stück": quantity,
            "Ø Kaufpreis": round(avg_price, 2),
            "Aktueller Preis": round(current_price_symbol, 2),
            "Einstand gesamt": round(total_cost, 2),
            "Marktwert": round(market_value, 2),
            "Offener PnL": round(open_pnl, 2),
            "Offener PnL %": round(open_pnl_pct, 2),
            "_trade_time": current_time_symbol
        })

    position_rows = sorted(
        position_rows,
        key=lambda x: x["Offener PnL"],
        reverse=True
    )

    return position_rows, total_positions_value


def get_position_card_class(pnl_value: float):
    if pnl_value > 0:
        return "em-card-positive", "Gewinn"
    elif pnl_value < 0:
        return "em-card-negative", "Verlust"
    return "", "Break-even"


def render_position_summary_metrics(position_rows, total_positions_value: float):
    total_open_pnl = sum(float(row["Offener PnL"]) for row in position_rows)
    total_cost_basis = sum(float(row["Einstand gesamt"]) for row in position_rows)
    total_open_pnl_pct = (total_open_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("Offene Positionen", len(position_rows))

    with metric_col2:
        st.metric("Marktwert", f"{total_positions_value:,.2f} €")

    with metric_col3:
        st.metric("Offener PnL", f"{total_open_pnl:,.2f} €")

    with metric_col4:
        st.metric("PnL %", f"{total_open_pnl_pct:.2f}%")


def render_position_card(position_row: dict):
    symbol = position_row["Symbol"]
    quantity = int(position_row["Stück"])
    current_price = float(position_row["Aktueller Preis"])
    trade_time = position_row["_trade_time"]
    pnl_value = float(position_row["Offener PnL"])

    card_class, pnl_label = get_position_card_class(pnl_value)
    fee_rate = st.session_state.fee_percent / 100

    st.markdown(
        f"""
        <div class="em-card {card_class}">
            <div class="em-card-title">{symbol}</div>
            <div class="em-card-sub">Stück: {quantity}</div>
            <div class="em-card-sub">Ø Kaufpreis: {position_row["Ø Kaufpreis"]:.2f} €</div>
            <div class="em-card-sub">Aktueller Preis: {position_row["Aktueller Preis"]:.2f} €</div>
            <div class="em-card-sub">Einstand gesamt: {position_row["Einstand gesamt"]:.2f} €</div>
            <div class="em-card-sub">Marktwert: {position_row["Marktwert"]:.2f} €</div>
            <div class="em-card-sub"><strong>{pnl_label}: {position_row["Offener PnL"]:.2f} € ({position_row["Offener PnL %"]:.2f}%)</strong></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    quick_col1, quick_col2, quick_col3 = st.columns(3)

    sell_25_qty = max(1, int(quantity * 0.25))
    sell_50_qty = max(1, int(quantity * 0.50))
    close_qty = quantity

    with quick_col1:
        if st.button("25% verkaufen", key=f"sell25_{symbol}", width="stretch"):
            qty_to_sell = min(sell_25_qty, quantity)
            success, message = execute_market_sell(
                symbol=symbol,
                quantity=qty_to_sell,
                current_price=current_price,
                trade_time=trade_time,
                fee_rate=fee_rate
            )
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with quick_col2:
        if st.button("50% verkaufen", key=f"sell50_{symbol}", width="stretch"):
            qty_to_sell = min(sell_50_qty, quantity)
            success, message = execute_market_sell(
                symbol=symbol,
                quantity=qty_to_sell,
                current_price=current_price,
                trade_time=trade_time,
                fee_rate=fee_rate
            )
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with quick_col3:
        if st.button("Position schließen", key=f"close_{symbol}", width="stretch"):
            success, message = execute_market_sell(
                symbol=symbol,
                quantity=close_qty,
                current_price=current_price,
                trade_time=trade_time,
                fee_rate=fee_rate
            )
            if success:
                st.success(f"{symbol} wurde vollständig verkauft.")
                st.rerun()
            else:
                st.error(message)

ORDER_TYPE_PRIORITY = {
    "Stop-Loss": 1,
    "Take-Profit": 2,
    "Trailing Stop": 3,
    "Limit Buy": 4,
    "Limit Sell": 5,
}


def get_order_badge_class(order_type: str) -> str:
    if order_type == "Limit Buy":
        return "em-badge-buy"
    if order_type == "Limit Sell":
        return "em-badge-sell"
    if order_type == "Stop-Loss":
        return "em-badge-sl"
    if order_type == "Take-Profit":
        return "em-badge-tp"
    if order_type == "Trailing Stop":
        return "em-badge-ts"
    return "em-badge-buy"


def sort_open_orders(orders_list: list) -> list:
    return sorted(
        orders_list,
        key=lambda order: (
            ORDER_TYPE_PRIORITY.get(order.get("Order Type", "Order"), 99),
            str(order.get("Symbol", "")),
            float(order.get("Limit Price", 0.0))
        )
    )


def build_open_orders_snapshot():
    prepared_orders = []

    for idx, order in enumerate(st.session_state.paper_open_orders):
        order_type = order.get("Order Type", "Order")
        symbol = order.get("Symbol", "-")
        quantity = int(order.get("Stück", 0))
        limit_price = float(order.get("Limit Price", 0.0))
        anchor_price = order.get("Anchor Price", None)

        prepared_orders.append({
            "original_index": idx,
            "Order Type": order_type,
            "Symbol": symbol,
            "Stück": quantity,
            "Limit Price": limit_price,
            "Anchor Price": anchor_price,
            "badge_class": get_order_badge_class(order_type),
        })

    return sort_open_orders(prepared_orders)


def render_open_orders_summary(orders_snapshot: list):
    order_count = len(orders_snapshot)
    symbols_count = len(set(order["Symbol"] for order in orders_snapshot))
    sl_tp_count = sum(
        1 for order in orders_snapshot
        if order["Order Type"] in ["Stop-Loss", "Take-Profit", "Trailing Stop"]
    )
    limit_count = sum(
        1 for order in orders_snapshot
        if order["Order Type"] in ["Limit Buy", "Limit Sell"]
    )

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("Offene Orders", order_count)

    with metric_col2:
        st.metric("Symbole", symbols_count)

    with metric_col3:
        st.metric("Schutz-Orders", sl_tp_count)

    with metric_col4:
        st.metric("Limit-Orders", limit_count)


def render_single_order_card(order: dict):
    order_type = order["Order Type"]
    symbol = order["Symbol"]
    quantity = order["Stück"]
    limit_price = order["Limit Price"]
    anchor_price = order["Anchor Price"]
    badge_class = order["badge_class"]
    original_index = order["original_index"]

    anchor_text = ""
    if anchor_price is not None:
        anchor_text = f"<div class='em-card-sub'>Anchor: {float(anchor_price):.2f} €</div>"

    st.markdown(
        f"""
        <div class="em-card">
            <div class="em-badge {badge_class}">{order_type}</div>
            <div class="em-card-title">{symbol}</div>
            <div class="em-card-sub">Stück: {quantity}</div>
            <div class="em-card-sub">Triggerpreis: {limit_price:.2f} €</div>
            {anchor_text}
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("❌ Order löschen", key=f"delete_order_{original_index}", width="stretch"):
        st.session_state.paper_open_orders.pop(original_index)
        st.success("Order gelöscht.")
        st.rerun()

def get_trade_card_class(realized_pnl):
    if realized_pnl is None:
        return "", "Neutral"
    if realized_pnl > 0:
        return "em-card-positive", "Gewinn"
    if realized_pnl < 0:
        return "em-card-negative", "Verlust"
    return "", "Break-even"


def build_trade_history_dataframe():
    if not st.session_state.paper_history:
        return pd.DataFrame()

    history_df = pd.DataFrame(st.session_state.paper_history).copy()

    if "Zeit" in history_df.columns:
        history_df["Zeit"] = pd.to_datetime(history_df["Zeit"], errors="coerce")

    if "Typ" not in history_df.columns:
        history_df["Typ"] = "Trade"

    if "Symbol" not in history_df.columns:
        history_df["Symbol"] = "-"

    if "Stück" not in history_df.columns:
        history_df["Stück"] = 0

    if "Preis" not in history_df.columns:
        history_df["Preis"] = 0.0

    if "Gebühr" not in history_df.columns:
        history_df["Gebühr"] = 0.0

    if "Gesamt" not in history_df.columns:
        history_df["Gesamt"] = 0.0

    if "Order" not in history_df.columns:
        history_df["Order"] = "-"

    if "Realized PnL" not in history_df.columns:
        history_df["Realized PnL"] = pd.NA

    history_df = history_df.sort_values("Zeit", ascending=False).reset_index(drop=True)
    return history_df


def render_trade_history_metrics(filtered_history_df: pd.DataFrame):
    trade_count = len(filtered_history_df)

    sell_df = filtered_history_df[
        filtered_history_df["Typ"].astype(str).str.lower() == "verkauf"
    ].copy()

    realized_pnl_sum = pd.to_numeric(
        sell_df["Realized PnL"], errors="coerce"
    ).fillna(0).sum()

    win_count = (pd.to_numeric(sell_df["Realized PnL"], errors="coerce") > 0).sum()
    closed_trade_count = len(sell_df)
    win_rate = (win_count / closed_trade_count * 100) if closed_trade_count > 0 else 0.0

    total_fees = pd.to_numeric(
        filtered_history_df["Gebühr"], errors="coerce"
    ).fillna(0).sum()

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("Trades", int(trade_count))

    with metric_col2:
        st.metric("Realisierter PnL", f"{realized_pnl_sum:,.2f} €")

    with metric_col3:
        st.metric("Win Rate", f"{win_rate:.2f}%")

    with metric_col4:
        st.metric("Gebühren", f"{total_fees:,.2f} €")


def render_trade_history_card(trade_row: dict, index_suffix: int):
    trade_type = str(trade_row.get("Typ", "-"))
    symbol = str(trade_row.get("Symbol", "-"))
    pieces = int(trade_row.get("Stück", 0))
    price = float(trade_row.get("Preis", 0.0))
    fee = float(trade_row.get("Gebühr", 0.0))
    total_value = float(trade_row.get("Gesamt", 0.0))
    order_type = str(trade_row.get("Order", "-"))
    trade_time = trade_row.get("Zeit", None)
    realized_pnl = trade_row.get("Realized PnL", pd.NA)

    realized_pnl_num = pd.to_numeric(pd.Series([realized_pnl]), errors="coerce").iloc[0]
    if pd.isna(realized_pnl_num):
        realized_pnl_num = None

    card_class, pnl_label = get_trade_card_class(realized_pnl_num)

    badge_class = "em-badge-buy" if trade_type.lower() == "kauf" else "em-badge-sell"

    if pd.notna(trade_time):
        try:
            formatted_time = pd.to_datetime(trade_time).strftime("%d.%m.%Y %H:%M")
        except Exception:
            formatted_time = str(trade_time)
    else:
        formatted_time = "-"

    pnl_line = ""
    if realized_pnl_num is not None:
        pnl_line = f"<div class='em-card-sub'><strong>{pnl_label}: {realized_pnl_num:.2f} €</strong></div>"

    st.markdown(
        f"""
        <div class="em-card {card_class}">
            <div class="em-badge {badge_class}">{trade_type}</div>
            <div class="em-card-title">{symbol}</div>
            <div class="em-card-sub">Zeit: {formatted_time}</div>
            <div class="em-card-sub">Stück: {pieces}</div>
            <div class="em-card-sub">Preis: {price:.2f} €</div>
            <div class="em-card-sub">Gebühr: {fee:.2f} €</div>
            <div class="em-card-sub">Gesamt: {total_value:.2f} €</div>
            <div class="em-card-sub">Order: {order_type}</div>
            {pnl_line}
        </div>
        """,
        unsafe_allow_html=True
    )

def build_equity_history_dataframe():
    if not st.session_state.paper_equity_history:
        return pd.DataFrame()

    equity_df = pd.DataFrame(st.session_state.paper_equity_history).copy()

    if "Zeit" in equity_df.columns:
        equity_df["Zeit"] = pd.to_datetime(equity_df["Zeit"], errors="coerce")

    required_cols = ["Cash", "Positionswert", "Gesamtwert"]
    for col in required_cols:
        if col not in equity_df.columns:
            equity_df[col] = 0.0

    equity_df = equity_df.dropna(subset=["Zeit"]).sort_values("Zeit").reset_index(drop=True)

    if not equity_df.empty:
        start_value = float(equity_df["Gesamtwert"].iloc[0])
        if start_value > 0:
            equity_df["Return %"] = ((equity_df["Gesamtwert"] / start_value) - 1) * 100
        else:
            equity_df["Return %"] = 0.0

        running_max = equity_df["Gesamtwert"].cummax()
        equity_df["Drawdown %"] = ((equity_df["Gesamtwert"] - running_max) / running_max) * 100
    else:
        equity_df["Return %"] = 0.0
        equity_df["Drawdown %"] = 0.0

    return equity_df


def get_benchmark_options():
    return ["SPY", "QQQ", "BTC-USD", "ETH-USD", "AAPL", "TSLA", "NVDA", "Custom"]


def load_benchmark_series(benchmark_symbol: str, period: str = "3mo", interval: str = "1d"):
    bench_data = load_data(benchmark_symbol, period=period, interval=interval)

    if bench_data.empty or "Close" not in bench_data.columns:
        return pd.DataFrame()

    bench_df = bench_data[["Close"]].copy().reset_index()

    time_col = bench_df.columns[0]
    bench_df = bench_df.rename(columns={time_col: "Zeit", "Close": "Benchmark Close"})
    bench_df["Zeit"] = pd.to_datetime(bench_df["Zeit"], errors="coerce")
    bench_df = bench_df.dropna(subset=["Zeit"]).sort_values("Zeit").reset_index(drop=True)

    if bench_df.empty:
        return pd.DataFrame()

    start_price = float(bench_df["Benchmark Close"].iloc[0])
    if start_price > 0:
        bench_df["Benchmark Return %"] = ((bench_df["Benchmark Close"] / start_price) - 1) * 100
    else:
        bench_df["Benchmark Return %"] = 0.0

    return bench_df


def merge_equity_with_benchmark(equity_df: pd.DataFrame, benchmark_df: pd.DataFrame):
    if equity_df.empty or benchmark_df.empty:
        return pd.DataFrame()

    compare_df = pd.merge_asof(
        equity_df.sort_values("Zeit"),
        benchmark_df.sort_values("Zeit"),
        on="Zeit",
        direction="nearest"
    )

    return compare_df


def render_equity_metrics(equity_df: pd.DataFrame):
    if equity_df.empty:
        return

    latest_total_value = float(equity_df["Gesamtwert"].iloc[-1])
    latest_cash = float(equity_df["Cash"].iloc[-1])
    latest_positions_value = float(equity_df["Positionswert"].iloc[-1])
    latest_return = float(equity_df["Return %"].iloc[-1])
    max_drawdown = float(equity_df["Drawdown %"].min())

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("Gesamtwert", f"{latest_total_value:,.2f} €")

    with metric_col2:
        st.metric("Cash", f"{latest_cash:,.2f} €")

    with metric_col3:
        st.metric("Return", f"{latest_return:.2f}%")

    with metric_col4:
        st.metric("Max Drawdown", f"{max_drawdown:.2f}%")


def create_equity_curve_figure(equity_df: pd.DataFrame):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=equity_df["Zeit"],
            y=equity_df["Gesamtwert"],
            mode="lines",
            name="Gesamtwert",
            line=dict(width=2.2, color="#42a5f5")
        )
    )

    fig.add_trace(
        go.Scatter(
            x=equity_df["Zeit"],
            y=equity_df["Cash"],
            mode="lines",
            name="Cash",
            line=dict(width=1.4, dash="dot", color="#26a69a")
        )
    )

    fig.add_trace(
        go.Scatter(
            x=equity_df["Zeit"],
            y=equity_df["Positionswert"],
            mode="lines",
            name="Positionswert",
            line=dict(width=1.4, dash="dot", color="#ab47bc")
        )
    )

    fig.update_layout(
        template="plotly_dark",
        height=420,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=TEXT_COLOR),
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis_title="Zeit",
        yaxis_title="Wert (€)"
    )
    fig.update_xaxes(gridcolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR)

    return fig


def create_benchmark_comparison_figure(compare_df: pd.DataFrame, benchmark_symbol: str):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=compare_df["Zeit"],
            y=compare_df["Return %"],
            mode="lines",
            name="Paper Trading",
            line=dict(width=2.4, color="#42a5f5")
        )
    )

    fig.add_trace(
        go.Scatter(
            x=compare_df["Zeit"],
            y=compare_df["Benchmark Return %"],
            mode="lines",
            name=benchmark_symbol,
            line=dict(width=2.0, color="#ff9800")
        )
    )

    fig.update_layout(
        template="plotly_dark",
        height=420,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=TEXT_COLOR),
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis_title="Zeit",
        yaxis_title="Performance (%)"
    )
    fig.update_xaxes(gridcolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR)

    return fig

def calculate_order_quantity_from_mode(
    mode: str,
    current_price: float,
    quantity_value: int,
    amount_value: float
):
    if current_price <= 0:
        return 0

    if mode == "Stückzahl":
        quantity = int(quantity_value)
    else:
        quantity = int(float(amount_value) / current_price)

    return max(0, quantity)


def create_order_payload(
    symbol: str,
    order_type: str,
    quantity: int,
    limit_price: float,
    anchor_price=None
):
    order_payload = {
        "Symbol": symbol,
        "Order Type": order_type,
        "Stück": int(quantity),
        "Limit Price": round(float(limit_price), 4)
    }

    if anchor_price is not None:
        order_payload["Anchor Price"] = round(float(anchor_price), 4)

    return order_payload


def add_open_order(order_payload: dict):
    st.session_state.paper_open_orders.append(order_payload)


def remove_existing_exit_orders_for_symbol(symbol: str):
    protected_types = {"Stop-Loss", "Take-Profit", "Trailing Stop"}
    st.session_state.paper_open_orders = [
        order for order in st.session_state.paper_open_orders
        if not (
            order.get("Symbol") == symbol
            and order.get("Order Type") in protected_types
        )
    ]


def render_advanced_order_preview_card(
    symbol: str,
    order_type: str,
    current_price: float,
    order_quantity: int,
    trigger_price: float | None,
    info_lines: list[str]
):
    trigger_text = "-"
    if trigger_price is not None:
        trigger_text = f"{trigger_price:.2f} €"

    details_html = "".join(
        [f"<div class='em-card-sub'>{line}</div>" for line in info_lines]
    )

    st.markdown(
        f"""
        <div class="em-card">
            <div class="em-card-title">{symbol}</div>
            <div class="em-card-sub">Order-Typ: {order_type}</div>
            <div class="em-card-sub">Aktueller Preis: {current_price:.2f} €</div>
            <div class="em-card-sub">Stück: {order_quantity}</div>
            <div class="em-card-sub">Trigger: {trigger_text}</div>
            {details_html}
        </div>
        """,
        unsafe_allow_html=True
    )

def format_euro(value):
    try:
        return f"{float(value):,.2f} €"
    except Exception:
        return "-"


def format_percent(value):
    try:
        return f"{float(value):.2f}%"
    except Exception:
        return "-"


def get_analysis_snapshot(data: pd.DataFrame):
    if data.empty:
        return {
            "last_close": 0.0,
            "prev_close": 0.0,
            "change_pct": 0.0,
            "day_range_pct": 0.0,
            "trend_label": "Neutral",
            "trend_color_class": "",
            "ema20": 0.0,
            "ema50": 0.0,
            "ema200": 0.0,
            "rsi": 0.0,
            "distance_to_ema20_pct": 0.0,
        }

    last_row = data.iloc[-1]
    prev_close = float(data["Close"].iloc[-2]) if len(data) > 1 else float(last_row["Close"])
    last_close = float(last_row["Close"])

    change_pct = ((last_close / prev_close) - 1) * 100 if prev_close > 0 else 0.0
    day_range_pct = ((float(last_row["High"]) - float(last_row["Low"])) / last_close) * 100 if last_close > 0 else 0.0

    ema20 = float(last_row.get("EMA20", 0.0))
    ema50 = float(last_row.get("EMA50", 0.0))
    ema200 = float(last_row.get("EMA200", 0.0))
    rsi = float(last_row.get("RSI", 0.0))

    if last_close > ema20 > ema50:
        trend_label = "Aufwärtstrend"
        trend_color_class = "em-card-positive"
    elif last_close < ema20 < ema50:
        trend_label = "Abwärtstrend"
        trend_color_class = "em-card-negative"
    else:
        trend_label = "Seitwärts / Übergang"
        trend_color_class = ""

    distance_to_ema20_pct = ((last_close / ema20) - 1) * 100 if ema20 > 0 else 0.0

    return {
        "last_close": last_close,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "day_range_pct": day_range_pct,
        "trend_label": trend_label,
        "trend_color_class": trend_color_class,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi": rsi,
        "distance_to_ema20_pct": distance_to_ema20_pct,
    }


def get_position_status_for_symbol(symbol: str):
    if symbol not in st.session_state.paper_positions:
        return {
            "has_position": False,
            "quantity": 0,
            "avg_price": 0.0,
            "market_value": 0.0,
            "open_pnl": 0.0,
            "open_pnl_pct": 0.0,
        }

    pos = st.session_state.paper_positions[symbol]
    quantity = int(pos.get("quantity", 0))
    avg_price = float(pos.get("avg_price", 0.0))
    total_cost = float(pos.get("total_cost", quantity * avg_price))

    current_price, _ = get_latest_price_for_symbol(symbol)
    if current_price is None:
        current_price = avg_price

    market_value = quantity * current_price
    open_pnl = market_value - total_cost
    open_pnl_pct = (open_pnl / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "has_position": True,
        "quantity": quantity,
        "avg_price": avg_price,
        "market_value": market_value,
        "open_pnl": open_pnl,
        "open_pnl_pct": open_pnl_pct,
    }


def render_analysis_intro_box():
    st.markdown(
        """
        <div class="em-section">
            <div class="em-kicker">Analysebereich</div>
            <div><strong>Einfacher Marktüberblick für schnelle Orientierung</strong></div>
            <div style="opacity:0.82; margin-top:0.25rem;">
                Schau zuerst auf Trend, Preis und wichtige Zonen. Alles Detaillierte wie RSI, MACD und Backtesting
                findest du weiter im Tab <strong>Advanced</strong>.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_analysis_learning_cards():
    learn_col1, learn_col2, learn_col3 = st.columns(3)

    with learn_col1:
        st.markdown(
            """
            <div class="em-card">
                <div class="em-card-title">1. Trend lesen</div>
                <div class="em-card-sub">EMA20 und EMA50 helfen dir, die Richtung schneller zu sehen.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with learn_col2:
        st.markdown(
            """
            <div class="em-card">
                <div class="em-card-title">2. Preiszonen prüfen</div>
                <div class="em-card-sub">Support, Resistance und Fibonacci zeigen mögliche Reaktionsbereiche.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with learn_col3:
        st.markdown(
            """
            <div class="em-card">
                <div class="em-card-title">3. Risiko klein halten</div>
                <div class="em-card-sub">SL, TP und kleine Positionsgrößen sind für Anfänger besonders wichtig.</div>
            </div>
            """,
            unsafe_allow_html=True
        )


def render_analysis_snapshot_metrics(snapshot: dict):
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("Aktueller Preis", format_euro(snapshot["last_close"]))

    with metric_col2:
        st.metric("Veränderung", format_percent(snapshot["change_pct"]))

    with metric_col3:
        st.metric("Tagesrange", format_percent(snapshot["day_range_pct"]))

    with metric_col4:
        st.metric("Trend", snapshot["trend_label"])


def render_analysis_indicator_cards(snapshot: dict, supports: list, resistances: list):
    left_col, right_col = st.columns([1.2, 1.0])

    nearest_support = supports[-1] if supports else None
    nearest_resistance = resistances[0] if resistances else None

    with left_col:
        trend_class = snapshot["trend_color_class"]

        support_text = f"{nearest_support:.2f} €" if nearest_support is not None else "-"
        resistance_text = f"{nearest_resistance:.2f} €" if nearest_resistance is not None else "-"

        st.markdown(
            f"""
            <div class="em-card {trend_class}">
                <div class="em-card-title">Marktstatus</div>
                <div class="em-card-sub">Trend: {snapshot["trend_label"]}</div>
                <div class="em-card-sub">EMA20: {snapshot["ema20"]:.2f}</div>
                <div class="em-card-sub">EMA50: {snapshot["ema50"]:.2f}</div>
                <div class="em-card-sub">EMA200: {snapshot["ema200"]:.2f}</div>
                <div class="em-card-sub">Abstand zu EMA20: {snapshot["distance_to_ema20_pct"]:.2f}%</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with right_col:
        st.markdown(
            f"""
            <div class="em-card">
                <div class="em-card-title">Wichtige Zonen</div>
                <div class="em-card-sub">Nächster Support: {support_text}</div>
                <div class="em-card-sub">Nächster Resistance: {resistance_text}</div>
                <div class="em-card-sub">RSI: {snapshot["rsi"]:.2f}</div>
                <div class="em-card-sub">Hinweis: RSI, MACD und Backtests findest du im Tab Advanced.</div>
            </div>
            """,
            unsafe_allow_html=True
        )


def render_analysis_position_card(symbol: str):
    position_status = get_position_status_for_symbol(symbol)

    st.write("### Aktueller Positionsstatus")

    if not position_status["has_position"]:
        st.info("Für dieses Symbol ist aktuell keine Paper-Trading-Position offen.")
        return

    pnl_class = "em-card-positive" if position_status["open_pnl"] > 0 else "em-card-negative" if position_status["open_pnl"] < 0 else ""

    st.markdown(
        f"""
        <div class="em-card {pnl_class}">
            <div class="em-card-title">{symbol}</div>
            <div class="em-card-sub">Stück: {position_status["quantity"]}</div>
            <div class="em-card-sub">Ø Kaufpreis: {position_status["avg_price"]:.2f} €</div>
            <div class="em-card-sub">Marktwert: {position_status["market_value"]:.2f} €</div>
            <div class="em-card-sub"><strong>Offener PnL: {position_status["open_pnl"]:.2f} € ({position_status["open_pnl_pct"]:.2f}%)</strong></div>
        </div>
        """,
        unsafe_allow_html=True
    )

def get_chart_colors_for_theme(chart_theme: str):
    if chart_theme == "Light":
        return {
            "template": "plotly_white",
            "paper_bgcolor": "rgba(255,255,255,0.90)",
            "plot_bgcolor": "rgba(255,255,255,0.98)",
            "font_color": "#182230",
            "grid_color": "rgba(20, 40, 70, 0.08)",
            "up_color": "#26a69a",
            "down_color": "#ef5350",
            "ema20_color": "#42a5f5",
            "ema50_color": "#ff9800",
            "ema200_color": "#ab47bc",
            "volume_color": "rgba(66, 165, 245, 0.35)",
            "support_color": "rgba(38, 166, 154, 0.45)",
            "resistance_color": "rgba(239, 83, 80, 0.45)",
            "fib_color": "rgba(255, 193, 7, 0.30)",
            "sl_color": "rgba(239, 83, 80, 0.85)",
            "tp_color": "rgba(38, 166, 154, 0.85)",
        }

    return {
        "template": "plotly_dark",
        "paper_bgcolor": CHART_BG,
        "plot_bgcolor": PLOT_BG,
        "font_color": TEXT_COLOR,
        "grid_color": GRID_COLOR,
        "up_color": "#26a69a",
        "down_color": "#ef5350",
        "ema20_color": "#42a5f5",
        "ema50_color": "#ff9800",
        "ema200_color": "#ab47bc",
        "volume_color": "rgba(66, 165, 245, 0.28)",
        "support_color": "rgba(38, 166, 154, 0.45)",
        "resistance_color": "rgba(239, 83, 80, 0.45)",
        "fib_color": "rgba(255, 193, 7, 0.25)",
        "sl_color": "rgba(239, 83, 80, 0.90)",
        "tp_color": "rgba(38, 166, 154, 0.90)",
    }


def get_fibonacci_levels_from_data(data: pd.DataFrame):
    if data.empty:
        return []

    recent_high = float(data["High"].max())
    recent_low = float(data["Low"].min())
    price_range = recent_high - recent_low

    if price_range <= 0:
        return []

    fib_ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
    fib_levels = []

    for ratio in fib_ratios:
        level_price = recent_high - (price_range * ratio)
        fib_levels.append({
            "ratio": ratio,
            "price": level_price
        })

    return fib_levels


def get_paper_trade_markers_for_symbol(symbol: str):
    buy_markers = []
    sell_markers = []

    for trade in st.session_state.paper_history:
        if str(trade.get("Symbol", "")) != symbol:
            continue

        trade_time = trade.get("Zeit")
        trade_price = trade.get("Preis")

        if trade_time is None or trade_price is None:
            continue

        trade_type = str(trade.get("Typ", "")).lower()

        if trade_type == "kauf":
            buy_markers.append({"Zeit": trade_time, "Preis": float(trade_price)})
        elif trade_type == "verkauf":
            sell_markers.append({
                "Zeit": trade_time,
                "Preis": float(trade_price),
                "PnL": trade.get("Realized PnL", None)
            })

    return pd.DataFrame(buy_markers), pd.DataFrame(sell_markers)


def get_open_exit_lines_for_symbol(symbol: str):
    sl_lines = []
    tp_lines = []

    for order in st.session_state.paper_open_orders:
        if str(order.get("Symbol", "")) != symbol:
            continue

        order_type = str(order.get("Order Type", ""))
        limit_price = float(order.get("Limit Price", 0.0))

        if limit_price <= 0:
            continue

        if order_type in ["Stop-Loss", "Trailing Stop"]:
            sl_lines.append({
                "label": order_type,
                "price": limit_price
            })
        elif order_type == "Take-Profit":
            tp_lines.append({
                "label": order_type,
                "price": limit_price
            })

    return sl_lines, tp_lines


def create_analysis_chart_figure(
    data: pd.DataFrame,
    ticker: str,
    chart_theme: str,
    show_ema: bool,
    show_fibonacci: bool,
    show_support_resistance: bool,
    show_volume: bool,
    show_trade_markers: bool,
    show_paper_markers: bool,
    show_sl_tp_orders: bool,
    supports: list,
    resistances: list,
    buy_df: pd.DataFrame,
    sell_df: pd.DataFrame
):
    colors = get_chart_colors_for_theme(chart_theme)

    has_volume = show_volume and "Volume" in data.columns
    row_heights = [0.78, 0.22] if has_volume else [1.0]

    fig = make_subplots(
        rows=2 if has_volume else 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=row_heights
    )

    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name=ticker,
            increasing_line_color="rgba(38,166,154,0.9)",
            decreasing_line_color="rgba(239,83,80,0.9)",
        ),
        row=1,
        col=1
    )

    if show_ema:
        fig.add_trace(
            go.Scatter(
                x=data.index, y=data["EMA20"],
                mode="lines",
                name="EMA20",
                line=dict(width=1.8, color=colors["ema20_color"])
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=data.index, y=data["EMA50"],
                mode="lines",
                name="EMA50",
                line=dict(width=1.8, color=colors["ema50_color"])
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=data.index, y=data["EMA200"],
                mode="lines",
                name="EMA200",
                line=dict(width=1.4, dash="dot", color=colors["ema200_color"])
            ),
            row=1, col=1
        )

    if show_support_resistance:
        for support in supports:
            fig.add_hline(
                y=float(support),
                line_width=1,
                line_dash="dot",
                line_color=colors["support_color"],
                annotation_text=f"Support {float(support):.2f}",
                annotation_position="bottom right",
                row=1, col=1
            )

        for resistance in resistances:
            fig.add_hline(
                y=float(resistance),
                line_width=1,
                line_dash="dot",
                line_color=colors["resistance_color"],
                annotation_text=f"Resistance {float(resistance):.2f}",
                annotation_position="top right",
                row=1, col=1
            )

    if show_fibonacci:
        fib_levels = get_fibonacci_levels_from_data(data)
        for fib in fib_levels:
            fig.add_hline(
                y=float(fib["price"]),
                line_width=1,
                line_dash="dash",
                line_color=colors["fib_color"],
                annotation_text=f"Fib {fib['ratio']:.3f}",
                annotation_position="left",
                row=1, col=1
            )

    if show_trade_markers and not buy_df.empty:
        fig.add_trace(
            go.Scatter(
                x=buy_df["Date"],
                y=buy_df["Price"],
                mode="markers",
                name="Backtest Buy",
                marker=dict(size=10, symbol="triangle-up", color="#42a5f5")
            ),
            row=1, col=1
        )

    if show_trade_markers and not sell_df.empty:
        fig.add_trace(
            go.Scatter(
                x=sell_df["Date"],
                y=sell_df["Price"],
                mode="markers",
                name="Backtest Sell",
                marker=dict(size=10, symbol="triangle-down", color="#ab47bc")
            ),
            row=1, col=1
        )

    paper_buy_df, paper_sell_df = get_paper_trade_markers_for_symbol(ticker)

    if show_paper_markers and not paper_buy_df.empty:
        fig.add_trace(
            go.Scatter(
                x=paper_buy_df["Zeit"],
                y=paper_buy_df["Preis"],
                mode="markers",
                name="Paper Buy",
                marker=dict(size=11, symbol="diamond", color="#26a69a")
            ),
            row=1, col=1
        )

    if show_paper_markers and not paper_sell_df.empty:
        hover_text = []
        for _, row_data in paper_sell_df.iterrows():
            pnl_value = row_data.get("PnL", None)
            if pnl_value is None or pd.isna(pnl_value):
                hover_text.append("Paper Sell")
            else:
                hover_text.append(f"Paper Sell<br>Realized PnL: {float(pnl_value):.2f} €")

        fig.add_trace(
            go.Scatter(
                x=paper_sell_df["Zeit"],
                y=paper_sell_df["Preis"],
                mode="markers",
                name="Paper Sell",
                marker=dict(size=11, symbol="diamond", color="#ef5350"),
                text=hover_text,
                hovertemplate="%{text}<extra></extra>"
            ),
            row=1, col=1
        )

    if show_sl_tp_orders:
        sl_lines, tp_lines = get_open_exit_lines_for_symbol(ticker)

        for sl_line in sl_lines:
            fig.add_hline(
                y=sl_line["price"],
                line_width=1.2,
                line_dash="dash",
                line_color=colors["sl_color"],
                annotation_text=sl_line["label"],
                annotation_position="right",
                row=1, col=1
            )

        for tp_line in tp_lines:
            fig.add_hline(
                y=tp_line["price"],
                line_width=1.2,
                line_dash="dash",
                line_color=colors["tp_color"],
                annotation_text=tp_line["label"],
                annotation_position="right",
                row=1, col=1
            )

    last_close = float(data["Close"].iloc[-1])

    fig.add_annotation(
        x=data.index[-1],
        y=last_close,
        text=f"{ticker}: {last_close:.2f} €",
        showarrow=True,
        arrowhead=1,
        ax=40,
        ay=-30,
        bgcolor="rgba(66,165,245,0.18)",
        bordercolor="rgba(66,165,245,0.45)",
        font=dict(size=11)
    )

    if has_volume:
        fig.add_trace(
            go.Bar(
                x=data.index,
                y=data["Volume"],
                name="Volumen",
                marker_color=colors["volume_color"]
            ),
            row=2, col=1
        )
        fig.update_yaxes(title_text="Volumen", row=2, col=1, gridcolor=colors["grid_color"])

    fig.update_layout(
        template=colors["template"],
        height=760 if has_volume else 620,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0
        ),
        xaxis_rangeslider_visible=False
    )

    fig.update_xaxes(
        gridcolor="rgba(120,180,255,0.08)",
        zerolinecolor="rgba(120,180,255,0.12)"
    )

    fig.update_yaxes(
        gridcolor="rgba(120,180,255,0.08)",
        zerolinecolor="rgba(120,180,255,0.12)"
    )

    return fig

def get_advanced_chart_colors(chart_theme: str):
    return get_chart_colors_for_theme(chart_theme)


def render_advanced_intro():
    st.markdown(
        """
        <div class="em-section">
            <div class="em-kicker">Advanced Bereich</div>
            <div><strong>Mehr Details für Indikatoren, Backtests und Strategie-Vergleiche</strong></div>
            <div style="opacity:0.82; margin-top:0.25rem;">
                Hier findest du RSI, MACD, Backtesting und Strategie-Vergleiche.
                Der Analyse-Tab bleibt bewusst einfacher für den schnellen Einstieg.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_advanced_top_metrics(data: pd.DataFrame):
    last_row = data.iloc[-1]

    current_rsi = float(last_row.get("RSI", 0.0))
    current_macd = float(last_row.get("MACD", 0.0))
    current_macd_signal = float(last_row.get("MACD_SIGNAL", 0.0))
    current_macd_hist = float(last_row.get("MACD_HIST", 0.0))

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("RSI", f"{current_rsi:.2f}")

    with metric_col2:
        st.metric("MACD", f"{current_macd:.4f}")

    with metric_col3:
        st.metric("MACD Signal", f"{current_macd_signal:.4f}")

    with metric_col4:
        st.metric("MACD Hist", f"{current_macd_hist:.4f}")


def create_rsi_figure(data: pd.DataFrame, chart_theme: str):
    colors = get_advanced_chart_colors(chart_theme)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["RSI"],
            mode="lines",
            name="RSI",
            line=dict(width=2.0, color=colors["ema20_color"])
        )
    )

    fig.add_hline(y=70, line_dash="dash", line_color=colors["resistance_color"], annotation_text="Überkauft")
    fig.add_hline(y=30, line_dash="dash", line_color=colors["support_color"], annotation_text="Überverkauft")
    fig.add_hline(y=50, line_dash="dot", line_color=colors["grid_color"], annotation_text="Neutral")

    fig.update_layout(
        template=colors["template"],
        height=300,
        paper_bgcolor=colors["paper_bgcolor"],
        plot_bgcolor=colors["plot_bgcolor"],
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis_title="Zeit",
        yaxis_title="RSI"
    )
    fig.update_xaxes(
        gridcolor="rgba(120,180,255,0.08)",
        zerolinecolor="rgba(120,180,255,0.12)"
    )

    fig.update_yaxes(
        gridcolor="rgba(120,180,255,0.08)",
        zerolinecolor="rgba(120,180,255,0.12)"
    )

    return fig


def create_macd_figure(data: pd.DataFrame, chart_theme: str):
    colors = get_advanced_chart_colors(chart_theme)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=data.index,
            y=data["MACD_HIST"],
            name="MACD Hist",
            marker_color="rgba(66, 165, 245, 0.45)"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["MACD"],
            mode="lines",
            name="MACD",
            line=dict(width=2.0, color=colors["ema20_color"])
        )
    )

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["MACD_SIGNAL"],
            mode="lines",
            name="MACD Signal",
            line=dict(width=1.8, color=colors["ema50_color"])
        )
    )

    fig.add_hline(y=0, line_dash="dot", line_color=colors["grid_color"])

    fig.update_layout(
        template=colors["template"],
        height=320,
        paper_bgcolor=colors["paper_bgcolor"],
        plot_bgcolor=colors["plot_bgcolor"],
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis_title="Zeit",
        yaxis_title="MACD"
    )
    fig.update_xaxes(
        gridcolor="rgba(120,180,255,0.08)",
        zerolinecolor="rgba(120,180,255,0.12)"
        )

    fig.update_yaxes(
        gridcolor="rgba(120,180,255,0.08)",
        zerolinecolor="rgba(120,180,255,0.12)"
    )

    return fig


def calc_backtest_summary(trades_df: pd.DataFrame, equity_df: pd.DataFrame, initial_capital: float):
    if trades_df.empty or equity_df.empty:
        return {
            "final_equity": initial_capital,
            "return_pct": 0.0,
            "win_rate": 0.0,
            "trades": 0,
            "avg_trade": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0
        }

    final_equity = float(equity_df["Equity"].iloc[-1])
    return_pct = ((final_equity / initial_capital) - 1) * 100
    win_rate = (trades_df["Trade Return After Fees %"] > 0).mean() * 100
    avg_trade = trades_df["Trade Return After Fees %"].mean()
    max_drawdown = calculate_max_drawdown(equity_df)

    wins = trades_df[trades_df["Trade Return After Fees %"] > 0]
    losses = trades_df[trades_df["Trade Return After Fees %"] < 0]

    total_profit = wins["Trade Return After Fees %"].sum() if not wins.empty else 0.0
    total_loss = abs(losses["Trade Return After Fees %"].sum()) if not losses.empty else 0.0
    profit_factor = (total_profit / total_loss) if total_loss > 0 else 0.0

    return {
        "final_equity": final_equity,
        "return_pct": return_pct,
        "win_rate": win_rate,
        "trades": len(trades_df),
        "avg_trade": avg_trade,
        "max_drawdown": max_drawdown,
        "profit_factor": profit_factor
    }


def render_backtest_metrics(summary: dict):
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("Endkapital", f"{summary['final_equity']:,.2f} €")

    with metric_col2:
        st.metric("Return", f"{summary['return_pct']:.2f}%")

    with metric_col3:
        st.metric("Win Rate", f"{summary['win_rate']:.2f}%")

    with metric_col4:
        st.metric("Trades", int(summary["trades"]))

    metric_col5, metric_col6, _, _ = st.columns(4)

    with metric_col5:
        st.metric("Ø Trade", f"{summary['avg_trade']:.2f}%")

    with metric_col6:
        st.metric("Max Drawdown", f"{summary['max_drawdown']:.2f}%")


def create_equity_comparison_figure(strategy_results: list, chart_theme: str):
    colors = get_advanced_chart_colors(chart_theme)

    fig = go.Figure()

    line_colors = [
        colors["ema20_color"],
        colors["ema50_color"],
        colors["ema200_color"],
        "#26a69a",
        "#ef5350"
    ]

    for i, result in enumerate(strategy_results):
        equity_df = result["equity_df"]
        name = result["name"]

        if equity_df.empty:
            continue

        x_col = "Date" if "Date" in equity_df.columns else equity_df.columns[0]
        y_col = "Equity" if "Equity" in equity_df.columns else equity_df.columns[-1]

        fig.add_trace(
            go.Scatter(
                x=equity_df[x_col],
                y=equity_df[y_col],
                mode="lines",
                name=name,
                line=dict(width=2.2, color=line_colors[i % len(line_colors)])
            )
        )

    fig.update_layout(
        template=colors["template"],
        height=420,
        paper_bgcolor=colors["paper_bgcolor"],
        plot_bgcolor=colors["plot_bgcolor"],
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis_title="Zeit",
        yaxis_title="Equity (€)"
    )
    fig.update_xaxes(
        gridcolor="rgba(120,180,255,0.08)",
        zerolinecolor="rgba(120,180,255,0.12)"
    )

    fig.update_yaxes(
        gridcolor="rgba(120,180,255,0.08)",
        zerolinecolor="rgba(120,180,255,0.12)"
    )

    return fig


def create_strategy_summary_dataframe(strategy_results: list, initial_capital: float):
    rows = []

    for result in strategy_results:
        summary = calc_backtest_summary(
            trades_df=result["trades_df"],
            equity_df=result["equity_df"],
            initial_capital=initial_capital
        )

        rows.append({
            "Strategie": result["name"],
            "Endkapital": round(summary["final_equity"], 2),
            "Return %": round(summary["return_pct"], 2),
            "Win Rate %": round(summary["win_rate"], 2),
            "Trades": int(summary["trades"]),
            "Ø Trade %": round(summary["avg_trade"], 2),
            "Max Drawdown %": round(summary["max_drawdown"], 2),
            "Profit Factor": round(summary["profit_factor"], 2),
        })

    return pd.DataFrame(rows)

def parse_compare_symbols(compare_text: str):
    symbols = []
    for item in str(compare_text).split(","):
        clean = item.strip().upper()
        if clean and clean not in symbols:
            symbols.append(clean)
    return symbols


def build_compare_dataset(symbols: list, period: str, interval: str):
    compare_rows = []
    normalized_frames = []

    for symbol in symbols:
        try:
            symbol_data = load_data(symbol, period=period, interval=interval)

            if symbol_data.empty:
                continue

            symbol_data = calculate_indicators(symbol_data)

            last_close = float(symbol_data["Close"].iloc[-1])
            first_close = float(symbol_data["Close"].iloc[0])
            prev_close = float(symbol_data["Close"].iloc[-2]) if len(symbol_data) > 1 else last_close

            return_pct = ((last_close / first_close) - 1) * 100 if first_close > 0 else 0.0
            day_change_pct = ((last_close / prev_close) - 1) * 100 if prev_close > 0 else 0.0

            ema20 = float(symbol_data["EMA20"].iloc[-1]) if "EMA20" in symbol_data.columns else 0.0
            ema50 = float(symbol_data["EMA50"].iloc[-1]) if "EMA50" in symbol_data.columns else 0.0
            rsi = float(symbol_data["RSI"].iloc[-1]) if "RSI" in symbol_data.columns else 0.0

            if last_close > ema20 > ema50:
                trend = "Aufwärtstrend"
            elif last_close < ema20 < ema50:
                trend = "Abwärtstrend"
            else:
                trend = "Seitwärts"

            compare_rows.append({
                "Symbol": symbol,
                "Preis": round(last_close, 2),
                "Performance %": round(return_pct, 2),
                "Tagesänderung %": round(day_change_pct, 2),
                "EMA20": round(ema20, 2),
                "EMA50": round(ema50, 2),
                "RSI": round(rsi, 2),
                "Trend": trend,
                "Kerzen": len(symbol_data)
            })

            norm_df = symbol_data[["Close"]].copy()
            norm_df = norm_df.rename(columns={"Close": symbol})
            first_value = float(norm_df[symbol].iloc[0])

            if first_value > 0:
                norm_df[symbol] = ((norm_df[symbol] / first_value) - 1) * 100
            else:
                norm_df[symbol] = 0.0

            normalized_frames.append(norm_df[[symbol]])

        except Exception:
            continue

    if normalized_frames:
        compare_chart_df = pd.concat(normalized_frames, axis=1).dropna(how="all")
        compare_chart_df = compare_chart_df.sort_index()
    else:
        compare_chart_df = pd.DataFrame()

    compare_df = pd.DataFrame(compare_rows)
    if not compare_df.empty:
        compare_df = compare_df.sort_values("Performance %", ascending=False).reset_index(drop=True)

    return compare_df, compare_chart_df


def render_compare_intro():
    st.markdown(
        """
        <div class="em-section">
            <div class="em-kicker">Vergleich</div>
            <div><strong>Mehrere Märkte auf einen Blick vergleichen</strong></div>
            <div style="opacity:0.82; margin-top:0.25rem;">
                Vergleiche Symbole nach Performance, Tagesänderung, Trend und RSI.
                So erkennst du schneller, welches Asset aktuell stärker oder schwächer läuft.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_compare_summary_metrics(compare_df: pd.DataFrame):
    if compare_df.empty:
        return

    best_symbol = compare_df.iloc[0]["Symbol"]
    best_perf = float(compare_df.iloc[0]["Performance %"])

    weakest_symbol = compare_df.iloc[-1]["Symbol"]
    weakest_perf = float(compare_df.iloc[-1]["Performance %"])

    avg_perf = float(compare_df["Performance %"].mean())
    avg_rsi = float(compare_df["RSI"].mean())

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("Beste Performance", f"{best_symbol} ({best_perf:.2f}%)")

    with metric_col2:
        st.metric("Schwächster Wert", f"{weakest_symbol} ({weakest_perf:.2f}%)")

    with metric_col3:
        st.metric("Ø Performance", f"{avg_perf:.2f}%")

    with metric_col4:
        st.metric("Ø RSI", f"{avg_rsi:.2f}")


def render_compare_cards(compare_df: pd.DataFrame):
    records = compare_df.to_dict("records")

    for i in range(0, len(records), 2):
        col1, col2 = st.columns(2)

        for col, record in zip([col1, col2], records[i:i+2]):
            pnl_class = "em-card-positive" if float(record["Performance %"]) > 0 else "em-card-negative" if float(record["Performance %"]) < 0 else ""

            with col:
                st.markdown(
                    f"""
                    <div class="em-card {pnl_class}">
                        <div class="em-card-title">{record["Symbol"]}</div>
                        <div class="em-card-sub">Preis: {record["Preis"]:.2f} €</div>
                        <div class="em-card-sub">Performance: {record["Performance %"]:.2f}%</div>
                        <div class="em-card-sub">Tagesänderung: {record["Tagesänderung %"]:.2f}%</div>
                        <div class="em-card-sub">Trend: {record["Trend"]}</div>
                        <div class="em-card-sub">RSI: {record["RSI"]:.2f}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


def create_compare_performance_figure(compare_chart_df: pd.DataFrame, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    fig = go.Figure()

    palette = [
        colors["ema20_color"],
        colors["ema50_color"],
        colors["ema200_color"],
        "#26a69a",
        "#ef5350",
        "#ff9800",
        "#7e57c2",
        "#29b6f6",
    ]

    for i, col_name in enumerate(compare_chart_df.columns):
        fig.add_trace(
            go.Scatter(
                x=compare_chart_df.index,
                y=compare_chart_df[col_name],
                mode="lines",
                name=col_name,
                line=dict(width=2.1, color=palette[i % len(palette)])
            )
        )

    fig.add_hline(y=0, line_dash="dot", line_color=colors["grid_color"])

    fig.update_layout(
        template=colors["template"],
        height=460,
        paper_bgcolor=colors["paper_bgcolor"],
        plot_bgcolor=colors["plot_bgcolor"],
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis_title="Zeit",
        yaxis_title="Performance seit Start (%)"
    )
    fig.update_xaxes(
        gridcolor="rgba(120,180,255,0.08)",
        zerolinecolor="rgba(120,180,255,0.12)"
    )

    fig.update_yaxes(
        gridcolor="rgba(120,180,255,0.08)",
        zerolinecolor="rgba(120,180,255,0.12)"
    )

    return fig

def build_watchlist_snapshot(watchlist_symbols: list, period: str = "1mo", interval: str = "1d"):
    rows = []

    for symbol in watchlist_symbols:
        try:
            symbol_data = load_data(symbol, period=period, interval=interval)

            if symbol_data.empty:
                continue

            symbol_data = calculate_indicators(symbol_data)

            last_close = float(symbol_data["Close"].iloc[-1])
            prev_close = float(symbol_data["Close"].iloc[-2]) if len(symbol_data) > 1 else last_close
            first_close = float(symbol_data["Close"].iloc[0])

            daily_change_pct = ((last_close / prev_close) - 1) * 100 if prev_close > 0 else 0.0
            period_change_pct = ((last_close / first_close) - 1) * 100 if first_close > 0 else 0.0

            ema20 = float(symbol_data["EMA20"].iloc[-1]) if "EMA20" in symbol_data.columns else 0.0
            ema50 = float(symbol_data["EMA50"].iloc[-1]) if "EMA50" in symbol_data.columns else 0.0
            rsi = float(symbol_data["RSI"].iloc[-1]) if "RSI" in symbol_data.columns else 0.0

            if last_close > ema20 > ema50:
                trend = "Aufwärtstrend"
            elif last_close < ema20 < ema50:
                trend = "Abwärtstrend"
            else:
                trend = "Seitwärts"

            rows.append({
                "Symbol": symbol,
                "Preis": round(last_close, 2),
                "Tagesänderung %": round(daily_change_pct, 2),
                "Performance %": round(period_change_pct, 2),
                "RSI": round(rsi, 2),
                "Trend": trend,
                "EMA20": round(ema20, 2),
                "EMA50": round(ema50, 2),
            })

        except Exception:
            continue

    watchlist_df = pd.DataFrame(rows)
    if not watchlist_df.empty:
        watchlist_df = watchlist_df.sort_values("Performance %", ascending=False).reset_index(drop=True)

    return watchlist_df


def render_watchlist_intro():
    st.markdown(
        """
        <div class="em-section">
            <div class="em-kicker">Watchlist</div>
            <div><strong>Behalte deine wichtigsten Märkte im Blick</strong></div>
            <div style="opacity:0.82; margin-top:0.25rem;">
                Füge hier Symbole hinzu, prüfe Preis, Trend und RSI und springe von dort direkt in Analyse oder Paper Trading.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_watchlist_summary_metrics(watchlist_df: pd.DataFrame):
    if watchlist_df.empty:
        return

    best_symbol = watchlist_df.iloc[0]["Symbol"]
    best_perf = float(watchlist_df.iloc[0]["Performance %"])

    worst_symbol = watchlist_df.iloc[-1]["Symbol"]
    worst_perf = float(watchlist_df.iloc[-1]["Performance %"])

    avg_rsi = float(watchlist_df["RSI"].mean())
    rising_count = int((watchlist_df["Trend"] == "Aufwärtstrend").sum())

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("Beste Performance", f"{best_symbol} ({best_perf:.2f}%)")

    with metric_col2:
        st.metric("Schwächster Wert", f"{worst_symbol} ({worst_perf:.2f}%)")

    with metric_col3:
        st.metric("Ø RSI", f"{avg_rsi:.2f}")

    with metric_col4:
        st.metric("Aufwärtstrends", rising_count)


def render_single_watchlist_card(row: dict):
    symbol = row["Symbol"]
    perf = float(row["Performance %"])
    card_class = "em-card-positive" if perf > 0 else "em-card-negative" if perf < 0 else ""

    st.markdown(
        f"""
        <div class="em-card {card_class}">
            <div class="em-card-title">{symbol}</div>
            <div class="em-card-sub">Preis: {row["Preis"]:.2f} €</div>
            <div class="em-card-sub">Tagesänderung: {row["Tagesänderung %"]:.2f}%</div>
            <div class="em-card-sub">Performance: {row["Performance %"]:.2f}%</div>
            <div class="em-card-sub">Trend: {row["Trend"]}</div>
            <div class="em-card-sub">RSI: {row["RSI"]:.2f}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    action_col1, action_col2, action_col3 = st.columns(3)

    with action_col1:
        if st.button("Analyse", key=f"watch_analyse_{symbol}", width="stretch"):
            st.session_state.ticker = symbol
            st.success(f"{symbol} wurde für die Analyse ausgewählt.")
            st.rerun()

    with action_col2:
        if st.button("Paper", key=f"watch_paper_{symbol}", width="stretch"):
            st.session_state.ticker = symbol
            st.success(f"{symbol} wurde für Paper Trading ausgewählt.")
            st.rerun()

    with action_col3:
        if st.button("Entfernen", key=f"watch_remove_{symbol}", width="stretch"):
            st.session_state.watchlist = [s for s in st.session_state.watchlist if s != symbol]
            save_watchlist(st.session_state.watchlist)
            st.success(f"{symbol} wurde aus der Watchlist entfernt.")
            st.rerun()

def section_title(title: str, caption: str | None = None):
    st.markdown(f'<div class="em-subsection-title">{title}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="em-subsection-caption">{caption}</div>', unsafe_allow_html=True)


def panel_box(title: str, subtitle: str | None = None):
    subtitle_html = f'<div class="em-panel-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="em-panel">
            <div class="em-panel-title">{title}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def vertical_gap(size: str = "md"):
    allowed = {"sm", "md", "lg"}
    size = size if size in allowed else "md"
    st.markdown(f'<div class="em-gap-{size}"></div>', unsafe_allow_html=True)

def apply_preset_to_session(preset_name: str):
    if preset_name not in PRESETS:
        return

    preset = PRESETS[preset_name]

    for key, value in preset.items():
        st.session_state[key] = value

    st.session_state.selected_preset_name = preset_name


def render_sidebar_panel(title: str, subtitle: str | None = None):
    subtitle_html = f'<div class="em-panel-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="em-panel">
            <div class="em-panel-title">{title}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def get_preset_description(preset_name: str):
    descriptions = {
        "Daytrading": "Kurzfristig, schneller, engeres Risiko.",
        "Swing Trading": "Ruhigerer Ansatz über mehrere Tage oder Wochen.",
        "Conservative": "Defensiver mit engerem Regelwerk.",
        "Aggressive": "Dynamischer mit mehr Risiko und mehr Bewegung.",
    }
    return descriptions.get(preset_name, "Vordefinierte Kombination für schnelleres Setup.")


def render_onboarding_guide():
    st.markdown(
        """
        <div class="em-section">
            <div class="em-kicker">Mini Guide</div>
            <div><strong>So startest du am einfachsten</strong></div>
            <div style="opacity:0.82; margin-top:0.35rem;">
                1. Symbol auswählen<br>
                2. Im Tab <strong>Analyse</strong> Trend und Zonen prüfen<br>
                3. Im Tab <strong>Paper Trading</strong> mit kleinem Betrag testen<br>
                4. Im Tab <strong>Advanced</strong> RSI, MACD und Backtest ansehen
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def classify_rsi_zone(rsi_value: float):
    if rsi_value >= 70:
        return "Überkauft"
    if rsi_value <= 30:
        return "Überverkauft"
    if rsi_value >= 55:
        return "Bullisch"
    if rsi_value <= 45:
        return "Eher schwach"
    return "Neutral"


def get_nearest_support_and_resistance(last_close: float, supports: list, resistances: list):
    nearest_support = None
    nearest_resistance = None

    if supports:
        support_candidates = [s for s in supports if s < last_close]
        if support_candidates:
            nearest_support = max(support_candidates)

    if resistances:
        resistance_candidates = [r for r in resistances if r > last_close]
        if resistance_candidates:
            nearest_resistance = min(resistance_candidates)

    return nearest_support, nearest_resistance


def build_learning_signal(snapshot: dict, supports: list, resistances: list):
    last_close = float(snapshot.get("last_close", 0.0))
    ema20 = float(snapshot.get("ema20", 0.0))
    ema50 = float(snapshot.get("ema50", 0.0))
    ema200 = float(snapshot.get("ema200", 0.0))
    rsi = float(snapshot.get("rsi", 50.0))

    nearest_support, nearest_resistance = get_nearest_support_and_resistance(
        last_close, supports, resistances
    )

    trend_up = last_close > ema20 > ema50
    trend_down = last_close < ema20 < ema50
    above_ema200 = last_close > ema200 if ema200 > 0 else False

    signal_title = "Kein klares Setup"
    signal_text = "Der Markt zeigt aktuell kein besonders sauberes Setup. Für Anfänger ist Abwarten hier oft sinnvoll."
    signal_type = "neutral"

    if trend_up and above_ema200 and 45 <= rsi <= 65:
        signal_title = "Trend Long – Rücksetzer beobachten"
        signal_text = (
            "Der Markt wirkt grundsätzlich stark. Für Anfänger kann es sinnvoll sein, "
            "auf einen ruhigeren Rücksetzer Richtung EMA20 oder Support zu warten statt direkt hinterher zu kaufen."
        )
        signal_type = "bullish"

    elif trend_up and rsi > 70:
        signal_title = "Trend stark, aber heiß gelaufen"
        signal_text = (
            "Der Trend ist positiv, aber der RSI ist bereits hoch. Ein sofortiger Einstieg ist oft riskanter. "
            "Warte eher auf eine Beruhigung oder einen Rücksetzer."
        )
        signal_type = "warning"

    elif trend_down and rsi < 45:
        signal_title = "Schwacher Markt – Vorsicht"
        signal_text = (
            "Der Markt wirkt schwach. Für Anfänger ist es oft besser, in so einer Lage nicht gegen den Trend zu handeln."
        )
        signal_type = "bearish"

    elif trend_down and rsi <= 30:
        signal_title = "Überverkauft – nur beobachten"
        signal_text = (
            "Der Markt ist schwach und bereits stark gefallen. Das kann zwar zu einer Gegenbewegung führen, "
            "ist für Anfänger aber oft schwer sauber zu handeln."
        )
        signal_type = "warning"

    risk_distance = None
    reward_distance = None

    if nearest_support is not None and last_close > 0:
        risk_distance = ((last_close - nearest_support) / last_close) * 100

    if nearest_resistance is not None and last_close > 0:
        reward_distance = ((nearest_resistance - last_close) / last_close) * 100

    return {
        "title": signal_title,
        "text": signal_text,
        "type": signal_type,
        "rsi_zone": classify_rsi_zone(rsi),
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "risk_distance_pct": risk_distance,
        "reward_distance_pct": reward_distance,
    }


def build_trade_idea(snapshot: dict, supports: list, resistances: list):
    last_close = float(snapshot.get("last_close", 0.0))
    ema20 = float(snapshot.get("ema20", 0.0))
    rsi = float(snapshot.get("rsi", 50.0))

    nearest_support, nearest_resistance = get_nearest_support_and_resistance(
        last_close, supports, resistances
    )

    direction = "Beobachten"
    entry = None
    stop_loss = None
    take_profit = None
    rr_ratio = None
    note = "Aktuell keine klare Lern-Idee."

    if nearest_support is not None and nearest_resistance is not None and last_close > ema20 and 40 <= rsi <= 68:
        direction = "Long Idee"
        entry = round(max(ema20, nearest_support * 1.003), 2)
        stop_loss = round(nearest_support * 0.995, 2)
        take_profit = round(nearest_resistance * 0.995, 2)

        risk = entry - stop_loss
        reward = take_profit - entry

        if risk > 0:
            rr_ratio = reward / risk

        note = (
            "Lernidee: In einem stabilen Aufwärtstrend könnte ein Einstieg näher an EMA20 oder Support sinnvoller sein "
            "als direkt am Hoch."
        )

    elif nearest_support is not None and last_close < ema20 and rsi < 45:
        direction = "Defensiv / Warten"
        entry = round(last_close, 2)
        stop_loss = round(nearest_support * 0.99, 2)
        take_profit = round(last_close * 1.03, 2)

        risk = entry - stop_loss
        reward = take_profit - entry

        if risk > 0:
            rr_ratio = reward / risk

        note = (
            "Der Markt ist eher schwach. Falls du trotzdem etwas üben willst, dann nur sehr defensiv und eher als Lernbeispiel."
        )

    return {
        "direction": direction,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rr_ratio": rr_ratio,
        "note": note,
    }


def render_learning_signal_box(signal: dict):
    signal_type = signal.get("type", "neutral")

    border_class = ""
    if signal_type == "bullish":
        border_class = "em-card-positive"
    elif signal_type == "bearish":
        border_class = "em-card-negative"

    nearest_support = signal.get("nearest_support")
    nearest_resistance = signal.get("nearest_resistance")

    support_text = f"{nearest_support:.2f} €" if nearest_support is not None else "-"
    resistance_text = f"{nearest_resistance:.2f} €" if nearest_resistance is not None else "-"

    risk_distance = signal.get("risk_distance_pct")
    reward_distance = signal.get("reward_distance_pct")

    risk_text = f"{risk_distance:.2f}%" if risk_distance is not None else "-"
    reward_text = f"{reward_distance:.2f}%" if reward_distance is not None else "-"

    st.markdown(
        f"""
        <div class="em-card {border_class}">
            <div class="em-card-title">Was könnte man jetzt tun?</div>
            <div class="em-card-sub"><strong>{signal["title"]}</strong></div>
            <div class="em-card-sub">{signal["text"]}</div>
            <div class="em-card-sub">RSI-Zone: {signal["rsi_zone"]}</div>
            <div class="em-card-sub">Nächster Support: {support_text}</div>
            <div class="em-card-sub">Nächste Resistance: {resistance_text}</div>
            <div class="em-card-sub">Abstand zum Support: {risk_text}</div>
            <div class="em-card-sub">Abstand zur Resistance: {reward_text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_trade_idea_box(trade_idea: dict, symbol: str):
    entry = trade_idea.get("entry")
    stop_loss = trade_idea.get("stop_loss")
    take_profit = trade_idea.get("take_profit")
    rr_ratio = trade_idea.get("rr_ratio")

    entry_text = f"{entry:.2f} €" if entry is not None else "-"
    stop_text = f"{stop_loss:.2f} €" if stop_loss is not None else "-"
    tp_text = f"{take_profit:.2f} €" if take_profit is not None else "-"
    rr_text = f"{rr_ratio:.2f}" if rr_ratio is not None else "-"

    st.markdown(
        f"""
        <div class="em-card">
            <div class="em-card-title">Mögliche Trade-Idee für {symbol}</div>
            <div class="em-card-sub">Richtung: {trade_idea["direction"]}</div>
            <div class="em-card-sub">Entry: {entry_text}</div>
            <div class="em-card-sub">Stop-Loss: {stop_text}</div>
            <div class="em-card-sub">Take-Profit: {tp_text}</div>
            <div class="em-card-sub">Chance / Risiko: {rr_text}</div>
            <div class="em-card-sub">{trade_idea["note"]}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def store_trade_idea_for_paper(symbol: str, trade_idea: dict):
    st.session_state.paper_trade_idea = {
        "symbol": symbol,
        "direction": trade_idea.get("direction"),
        "entry": trade_idea.get("entry"),
        "stop_loss": trade_idea.get("stop_loss"),
        "take_profit": trade_idea.get("take_profit"),
        "rr_ratio": trade_idea.get("rr_ratio"),
        "note": trade_idea.get("note"),
    }


def render_trade_idea_quick_actions(symbol: str, trade_idea: dict):
    if trade_idea.get("entry") is None:
        st.info("Für die aktuelle Marktlage konnte keine konkrete Lern-Trade-Idee vorbereitet werden.")
        return

    action_col1, action_col2 = st.columns(2)

    with action_col1:
        if st.button("Trade-Idee merken", key=f"store_trade_idea_{symbol}", width="stretch"):
            store_trade_idea_for_paper(symbol, trade_idea)
            st.success("Die Trade-Idee wurde für Paper Trading vorbereitet.")

    with action_col2:
        if st.button("SL / TP in Paper Trading vorbereiten", key=f"prepare_trade_idea_{symbol}", width="stretch"):
            store_trade_idea_for_paper(symbol, trade_idea)
            st.session_state.trade_idea_prefill_sl = trade_idea.get("stop_loss")
            st.session_state.trade_idea_prefill_tp = trade_idea.get("take_profit")
            st.success("SL / TP wurden für Paper Trading vorgemerkt.")


def render_paper_trade_idea_box():
    trade_idea = st.session_state.get("paper_trade_idea")

    if not trade_idea:
        return

    entry = trade_idea.get("entry")
    stop_loss = trade_idea.get("stop_loss")
    take_profit = trade_idea.get("take_profit")
    rr_ratio = trade_idea.get("rr_ratio")

    entry_text = f"{entry:.2f} €" if entry is not None else "-"
    stop_text = f"{stop_loss:.2f} €" if stop_loss is not None else "-"
    tp_text = f"{take_profit:.2f} €" if take_profit is not None else "-"
    rr_text = f"{rr_ratio:.2f}" if rr_ratio is not None else "-"

    st.markdown(
        f"""
        <div class="em-card">
            <div class="em-card-title">Gemerkte Lern-Trade-Idee</div>
            <div class="em-card-sub">Symbol: {trade_idea.get("symbol", "-")}</div>
            <div class="em-card-sub">Richtung: {trade_idea.get("direction", "-")}</div>
            <div class="em-card-sub">Entry: {entry_text}</div>
            <div class="em-card-sub">Stop-Loss: {stop_text}</div>
            <div class="em-card-sub">Take-Profit: {tp_text}</div>
            <div class="em-card-sub">Chance / Risiko: {rr_text}</div>
            <div class="em-card-sub">{trade_idea.get("note", "")}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("Gemerkte Idee löschen", key="clear_paper_trade_idea", width="stretch"):
        st.session_state.paper_trade_idea = None
        st.success("Die gemerkte Trade-Idee wurde gelöscht.")
        st.rerun()

def normalize_trade_quantity(quantity_value) -> float:
    try:
        quantity = round(float(quantity_value), 6)
    except Exception:
        return 0.0
    return max(0.0, quantity)


def get_current_fee_rate() -> float:
    return float(st.session_state.fee_percent) / 100


def ensure_symbol_position(symbol: str):
    if symbol not in st.session_state.paper_positions:
        st.session_state.paper_positions[symbol] = {
            "quantity": 0,
            "avg_price": 0.0,
            "total_cost": 0.0
        }


def add_trade_to_history(
    trade_time,
    trade_type: str,
    symbol: str,
    quantity: int,
    price: float,
    fee: float,
    total_value: float,
    order_name: str,
    realized_pnl=None
):
    payload = {
        "Zeit": trade_time,
        "Typ": trade_type,
        "Symbol": symbol,
        "Stück": round(float(quantity), 6),
        "Preis": round(float(price), 2),
        "Gebühr": round(float(fee), 2),
        "Gesamt": round(float(total_value), 2),
        "Order": order_name,
        "Risiko-Profil": get_active_risk_profile_name()
    }

    if realized_pnl is not None:
        payload["Realized PnL"] = round(float(realized_pnl), 2)

    st.session_state.paper_history.append(payload)

    


def execute_paper_buy(symbol: str, quantity_value, price: float, trade_time, order_name: str = "Market Buy"):
    quantity = normalize_trade_quantity(quantity_value)

    if quantity < 1:
        return False, "Bitte eine gültige Stückzahl eingeben."

    fee_rate = get_current_fee_rate()
    gross_cost = float(price) * quantity
    fee_cost = gross_cost * fee_rate
    total_cost = gross_cost + fee_cost

    if st.session_state.paper_cash < total_cost:
        return False, "Nicht genug Cash für diesen Kauf."

    ensure_symbol_position(symbol)

    old_qty = float(st.session_state.paper_positions[symbol]["quantity"])
    old_total_cost = float(st.session_state.paper_positions[symbol]["total_cost"])

    new_qty = old_qty + quantity
    new_total_cost = old_total_cost + total_cost
    new_avg_price = new_total_cost / new_qty if new_qty > 0 else 0.0

    st.session_state.paper_positions[symbol]["quantity"] = new_qty
    st.session_state.paper_positions[symbol]["avg_price"] = new_avg_price
    st.session_state.paper_positions[symbol]["total_cost"] = new_total_cost

    st.session_state.paper_cash -= total_cost

    add_trade_to_history(
        trade_time=trade_time,
        trade_type="Kauf",
        symbol=symbol,
        quantity=quantity,
        price=price,
        fee=fee_cost,
        total_value=total_cost,
        order_name=order_name
    )

    update_paper_equity_snapshot()
    return True, f"{quantity} Stück {symbol} wurden gekauft."


def execute_paper_sell(symbol: str, quantity_value, price: float, trade_time, order_name: str = "Market Sell"):
    quantity = normalize_trade_quantity(quantity_value)

    if quantity < 0:
        return False, "Bitte eine gültige Stückzahl eingeben."

    if symbol not in st.session_state.paper_positions:
        return False, "Für dieses Symbol ist keine Position offen."

    position = st.session_state.paper_positions[symbol]
    held_qty = float(position["quantity"])

    if held_qty < quantity:
        return False, "Nicht genug Stück in der Position."

    fee_rate = get_current_fee_rate()
    gross_value = float(price) * quantity
    fee_cost = gross_value * fee_rate
    net_value = gross_value - fee_cost

    avg_price = float(position["avg_price"])
    total_position_cost = float(position["total_cost"])

    cost_basis_sold = avg_price * quantity
    realized_pnl = net_value - cost_basis_sold

    st.session_state.paper_cash += net_value

    remaining_qty = held_qty - quantity
    remaining_total_cost = total_position_cost - cost_basis_sold

    if remaining_qty > 0:
        st.session_state.paper_positions[symbol]["quantity"] = remaining_qty
        st.session_state.paper_positions[symbol]["total_cost"] = remaining_total_cost
        st.session_state.paper_positions[symbol]["avg_price"] = (
            remaining_total_cost / remaining_qty if remaining_qty > 0 else 0.0
        )
    else:
        del st.session_state.paper_positions[symbol]

    add_trade_to_history(
        trade_time=trade_time,
        trade_type="Verkauf",
        symbol=symbol,
        quantity=quantity,
        price=price,
        fee=fee_cost,
        total_value=net_value,
        order_name=order_name,
        realized_pnl=realized_pnl
    )

    update_paper_equity_snapshot()
    return True, f"{quantity} Stück {symbol} wurden verkauft."


def add_exit_orders_after_buy(symbol: str, quantity_value, stop_loss_value, take_profit_value):
    quantity = normalize_trade_quantity(quantity_value)

    if quantity < 1:
        return

    if stop_loss_value and float(stop_loss_value) > 0:
        st.session_state.paper_open_orders.append({
            "Symbol": symbol,
            "Order Type": "Stop-Loss",
            "Stück": quantity,
            "Limit Price": round(float(stop_loss_value), 4)
        })

    if take_profit_value and float(take_profit_value) > 0:
        st.session_state.paper_open_orders.append({
            "Symbol": symbol,
            "Order Type": "Take-Profit",
            "Stück": quantity,
            "Limit Price": round(float(take_profit_value), 4)
        })


def get_open_position_for_symbol(symbol: str):
    if symbol not in st.session_state.paper_positions:
        return None

    return st.session_state.paper_positions[symbol]


def get_position_pnl_for_symbol(symbol: str, current_price: float):
    position = get_open_position_for_symbol(symbol)

    if not position:
        return 0.0, 0.0

    quantity = float(position["quantity"])
    avg_price = float(position["avg_price"])

    pnl_value = (current_price - avg_price) * quantity
    pnl_pct = ((current_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0.0

    return pnl_value, pnl_pct

def get_orders_for_symbol(symbol: str):
    return [o for o in st.session_state.paper_open_orders if o.get("Symbol") == symbol]


def remove_orders_for_symbol(symbol: str, types: list = None):
    if types is None:
        st.session_state.paper_open_orders = [
            o for o in st.session_state.paper_open_orders
            if o.get("Symbol") != symbol
        ]
    else:
        st.session_state.paper_open_orders = [
            o for o in st.session_state.paper_open_orders
            if not (o.get("Symbol") == symbol and o.get("Order Type") in types)
        ]


def remove_exit_orders_for_symbol(symbol: str):
    # Entfernt SL/TP/Trailing
    remove_orders_for_symbol(symbol, types=["Stop-Loss", "Take-Profit", "Trailing"])


def remove_invalid_orders():
    cleaned = []
    for o in st.session_state.paper_open_orders:
        if not o.get("Symbol"):
            continue
        if float(o.get("Stück", 0)) <= 0:
            continue
        if o.get("Order Type") in ["Limit Buy", "Limit Sell", "Stop-Loss", "Take-Profit"]:
            if float(o.get("Limit Price", 0)) <= 0:
                continue
        cleaned.append(o)
    st.session_state.paper_open_orders = cleaned

def handle_oco_after_fill(symbol: str, filled_type: str):
    # Wenn TP ausgelöst → SL löschen, und umgekehrt
    if filled_type == "Take-Profit":
        remove_orders_for_symbol(symbol, types=["Stop-Loss", "Trailing"])
    elif filled_type == "Stop-Loss":
        remove_orders_for_symbol(symbol, types=["Take-Profit", "Trailing"])


def process_open_orders_for_symbol(symbol: str, current_price: float, trade_time):
    # Wir iterieren auf einer Kopie, da wir die Liste verändern
    orders = list(get_orders_for_symbol(symbol))

    for order in orders:
        otype = order.get("Order Type")
        qty = int(order.get("Stück", 0))
        limit_price = float(order.get("Limit Price", 0))

        # -------- LIMIT BUY --------
        if otype == "Limit Buy" and current_price <= limit_price:
            success, _ = execute_paper_buy(
                symbol=symbol,
                quantity_value=qty,
                price=current_price,
                trade_time=trade_time,
                order_name="Limit Buy"
            )
            if success:
                st.session_state.paper_open_orders.remove(order)

        # -------- LIMIT SELL --------
        elif otype == "Limit Sell" and current_price >= limit_price:
            success, _ = execute_paper_sell(
                symbol=symbol,
                quantity_value=qty,
                price=current_price,
                trade_time=trade_time,
                order_name="Limit Sell"
            )
            if success:
                st.session_state.paper_open_orders.remove(order)

        # -------- STOP LOSS --------
        elif otype == "Stop-Loss" and current_price <= limit_price:
            success, _ = execute_paper_sell(
                symbol=symbol,
                quantity_value=qty,
                price=current_price,
                trade_time=trade_time,
                order_name="Stop-Loss"
            )
            if success:
                st.session_state.paper_open_orders.remove(order)
                handle_oco_after_fill(symbol, "Stop-Loss")

        # -------- TAKE PROFIT --------
        elif otype == "Take-Profit" and current_price >= limit_price:
            success, _ = execute_paper_sell(
                symbol=symbol,
                quantity_value=qty,
                price=current_price,
                trade_time=trade_time,
                order_name="Take-Profit"
            )
            if success:
                st.session_state.paper_open_orders.remove(order)
                handle_oco_after_fill(symbol, "Take-Profit")

        # -------- TRAILING STOP --------
        elif otype == "Trailing":
            trail_pct = float(order.get("Trail %", 0))
            if trail_pct <= 0:
                continue

            # wir speichern den höchsten Preis im Order selbst
            high_key = "Trail High"
            prev_high = float(order.get(high_key, current_price))
            new_high = max(prev_high, current_price)
            order[high_key] = new_high

            trigger_price = new_high * (1 - trail_pct / 100)

            if current_price <= trigger_price:
                success, _ = execute_paper_sell(
                    symbol=symbol,
                    quantity_value=qty,
                    price=current_price,
                    trade_time=trade_time,
                    order_name="Trailing Stop"
                )
                if success:
                    st.session_state.paper_open_orders.remove(order)
                    handle_oco_after_fill(symbol, "Stop-Loss")


def process_all_open_orders(current_price_map: dict, trade_time):
    # current_price_map: {"AAPL": 123.4, ...}
    symbols = set([o.get("Symbol") for o in st.session_state.paper_open_orders if o.get("Symbol")])

    for sym in symbols:
        price = current_price_map.get(sym)
        if price is None:
            continue
        process_open_orders_for_symbol(sym, price, trade_time)

    # Cleanup danach
    remove_invalid_orders()

    # Wenn Position komplett geschlossen → Exit Orders entfernen
    active_symbols = set(st.session_state.paper_positions.keys())
    st.session_state.paper_open_orders = [
        o for o in st.session_state.paper_open_orders
        if not (o.get("Symbol") not in active_symbols and o.get("Order Type") in ["Stop-Loss", "Take-Profit", "Trailing"])
    ]

def render_open_orders_ui():
    st.markdown("### Offene Orders")

    if not st.session_state.paper_open_orders:
        st.info("Keine offenen Orders.")
        return

    for i, o in enumerate(st.session_state.paper_open_orders):
        sym = o.get("Symbol")
        otype = o.get("Order Type")
        qty = int(o.get("Stück", 0))
        price = o.get("Limit Price")

        badge = {
            "Stop-Loss": "🔴 SL",
            "Take-Profit": "🟢 TP",
            "Limit Buy": "🟦 Buy",
            "Limit Sell": "🟧 Sell",
            "Trailing": "🟣 Trail"
        }.get(otype, "Order")

        price_text = f"{price:.2f} €" if price else "-"

        st.markdown(
            f"""
            <div class="em-card">
                <div class="em-card-title">{badge} – {sym}</div>
                <div class="em-card-sub">Typ: {otype}</div>
                <div class="em-card-sub">Stück: {qty}</div>
                <div class="em-card-sub">Preis: {price_text}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button("Order löschen", key=f"del_order_{i}", width="stretch"):
            st.session_state.paper_open_orders.remove(o)
            st.rerun()

def build_trade_journal_dataframe():
    if not st.session_state.paper_history:
        return pd.DataFrame()

    df = pd.DataFrame(st.session_state.paper_history).copy()

    if "Zeit" in df.columns:
        df["Zeit"] = pd.to_datetime(df["Zeit"], errors="coerce")

    for col in ["Gebühr", "Gesamt", "Preis", "Stück", "Realized PnL"]:
        if col not in df.columns:
            df[col] = 0.0

    df["Gebühr"] = pd.to_numeric(df["Gebühr"], errors="coerce").fillna(0.0)
    df["Gesamt"] = pd.to_numeric(df["Gesamt"], errors="coerce").fillna(0.0)
    df["Preis"] = pd.to_numeric(df["Preis"], errors="coerce").fillna(0.0)
    df["Stück"] = pd.to_numeric(df["Stück"], errors="coerce").fillna(0.0)
    df["Realized PnL"] = pd.to_numeric(df["Realized PnL"], errors="coerce")

    return df.sort_values("Zeit", ascending=False).reset_index(drop=True)


def build_closed_trades_review_df(history_df: pd.DataFrame):
    if history_df.empty:
        return pd.DataFrame()

    sells = history_df[history_df["Typ"].astype(str).str.lower() == "verkauf"].copy()
    if sells.empty:
        return pd.DataFrame()

    sells["Result"] = sells["Realized PnL"].apply(
        lambda x: "Gewinn" if pd.notna(x) and x > 0 else "Verlust" if pd.notna(x) and x < 0 else "Neutral"
    )

    sells["Realized PnL % (approx)"] = sells.apply(
        lambda row: ((row["Realized PnL"] / row["Gesamt"]) * 100) if pd.notna(row["Realized PnL"]) and row["Gesamt"] > 0 else 0.0,
        axis=1
    )

    return sells.reset_index(drop=True)


def calculate_trade_journal_metrics(review_df: pd.DataFrame, history_df: pd.DataFrame):
    if review_df.empty:
        return {
            "closed_trades": 0,
            "win_rate": 0.0,
            "gross_realized_pnl": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "total_fees": float(history_df["Gebühr"].sum()) if not history_df.empty else 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
        }

    wins = review_df[review_df["Realized PnL"] > 0].copy()
    losses = review_df[review_df["Realized PnL"] < 0].copy()

    gross_realized_pnl = float(review_df["Realized PnL"].fillna(0).sum())
    closed_trades = int(len(review_df))
    win_rate = float((review_df["Realized PnL"] > 0).mean() * 100) if closed_trades > 0 else 0.0
    avg_win = float(wins["Realized PnL"].mean()) if not wins.empty else 0.0
    avg_loss = float(losses["Realized PnL"].mean()) if not losses.empty else 0.0

    total_profit = float(wins["Realized PnL"].sum()) if not wins.empty else 0.0
    total_loss = abs(float(losses["Realized PnL"].sum())) if not losses.empty else 0.0
    profit_factor = (total_profit / total_loss) if total_loss > 0 else 0.0

    total_fees = float(history_df["Gebühr"].sum()) if not history_df.empty else 0.0
    best_trade = float(review_df["Realized PnL"].max()) if not review_df.empty else 0.0
    worst_trade = float(review_df["Realized PnL"].min()) if not review_df.empty else 0.0

    return {
        "closed_trades": closed_trades,
        "win_rate": win_rate,
        "gross_realized_pnl": gross_realized_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "total_fees": total_fees,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
    }


def build_symbol_review_summary(review_df: pd.DataFrame):
    if review_df.empty:
        return pd.DataFrame()

    grouped = review_df.groupby("Symbol", dropna=False).agg(
        Trades=("Symbol", "count"),
        RealizedPnL=("Realized PnL", "sum"),
        AvgPnL=("Realized PnL", "mean"),
        WinRate=("Realized PnL", lambda s: (s > 0).mean() * 100),
    ).reset_index()

    grouped = grouped.rename(columns={
        "RealizedPnL": "Realized PnL",
        "AvgPnL": "Ø PnL",
        "WinRate": "Win Rate %"
    })

    return grouped.sort_values("Realized PnL", ascending=False).reset_index(drop=True)


def create_journal_pnl_figure(review_df: pd.DataFrame, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=review_df.index.astype(str),
            y=review_df["Realized PnL"].fillna(0),
            name="Trade PnL"
        )
    )

    fig.add_hline(y=0, line_dash="dot", line_color=colors["grid_color"])

    fig.update_layout(
        template=colors["template"],
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="Geschlossene Trades",
        yaxis_title="Realized PnL (€)",
        showlegend=False
    )
    fig.update_xaxes(gridcolor="rgba(120,180,255,0.08)")
    fig.update_yaxes(gridcolor="rgba(120,180,255,0.08)")

    return fig


def get_journal_feedback(metrics: dict):
    feedback = []

    if metrics["closed_trades"] < 5:
        feedback.append("Noch wenige abgeschlossene Trades – für eine faire Auswertung brauchst du etwas mehr Daten.")
    if metrics["win_rate"] >= 55:
        feedback.append("Die Trefferquote wirkt solide. Jetzt ist wichtig, ob deine Gewinne auch groß genug sind.")
    elif metrics["win_rate"] < 40 and metrics["closed_trades"] >= 5:
        feedback.append("Die Trefferquote ist noch niedrig. Prüfe, ob du zu früh einsteigst oder gegen den Trend handelst.")
    if metrics["profit_factor"] >= 1.3:
        feedback.append("Dein Profit Factor ist ordentlich. Das ist oft wichtiger als nur die Win Rate.")
    elif 0 < metrics["profit_factor"] < 1.0:
        feedback.append("Dein Profit Factor liegt unter 1. Das heißt: Verluste fressen aktuell Gewinne auf.")
    if abs(metrics["total_fees"]) > 0 and metrics["gross_realized_pnl"] > 0 and metrics["total_fees"] > metrics["gross_realized_pnl"] * 0.35:
        feedback.append("Die Gebühren sind relativ hoch im Verhältnis zum Gewinn. Vielleicht handelst du zu häufig.")
    if metrics["avg_loss"] < 0 and metrics["avg_win"] > 0 and abs(metrics["avg_loss"]) > metrics["avg_win"]:
        feedback.append("Deine durchschnittlichen Verluste sind größer als deine durchschnittlichen Gewinne. SL / Exits prüfen.")
    if not feedback:
        feedback.append("Solider Start. Beobachte weiter Trefferquote, Gebühren und das Verhältnis von Gewinn zu Verlust.")

    return feedback


def render_trade_journal_metrics(metrics: dict):
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("Geschlossene Trades", metrics["closed_trades"])

    with m2:
        st.metric("Win Rate", f"{metrics['win_rate']:.2f}%")

    with m3:
        st.metric("Realized PnL", f"{metrics['gross_realized_pnl']:.2f} €")

    with m4:
        st.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")

    m5, m6, m7, m8 = st.columns(4)

    with m5:
        st.metric("Ø Gewinn", f"{metrics['avg_win']:.2f} €")

    with m6:
        st.metric("Ø Verlust", f"{metrics['avg_loss']:.2f} €")

    with m7:
        st.metric("Beste Trade", f"{metrics['best_trade']:.2f} €")

    with m8:
        st.metric("Gebühren gesamt", f"{metrics['total_fees']:.2f} €")


def render_trade_journal_feedback(feedback_lines: list):
    for line in feedback_lines:
        st.markdown(
            f"""
            <div class="em-card">
                <div class="em-card-title">Review-Hinweis</div>
                <div class="em-card-sub">{line}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

def render_trade_history_simple():
    st.write("### Trade Historie")
    st.caption("Hier siehst du alle bisherigen virtuellen Käufe und Verkäufe.")

    if not st.session_state.paper_history:
        st.info("Noch keine Trades in der Historie vorhanden.")
        return

    history_df = pd.DataFrame(st.session_state.paper_history).copy()

    if "Zeit" in history_df.columns:
        history_df["Zeit"] = pd.to_datetime(history_df["Zeit"], errors="coerce")
        history_df = history_df.sort_values("Zeit", ascending=False)

    recent_cards_df = history_df.head(6).copy()

    if not recent_cards_df.empty:
        for i in range(0, len(recent_cards_df), 2):
            col1, col2 = st.columns(2)

            row_left = recent_cards_df.iloc[i]

            with col1:
                trade_type = str(row_left.get("Typ", "-"))
                symbol = str(row_left.get("Symbol", "-"))
                fee = float(row_left.get("Gebühr", 0.0))
                total_value = float(row_left.get("Gesamt", 0.0))
                price = float(row_left.get("Preis", 0.0))
                pieces = int(float(row_left.get("Stück", 0)))
                realized = row_left.get("Realized PnL", None)

                badge_class = "em-badge-buy" if trade_type.lower() == "kauf" else "em-badge-sell"
                border_class = ""
                if pd.notna(realized) and float(realized) > 0:
                    border_class = "em-card-positive"
                elif pd.notna(realized) and float(realized) < 0:
                    border_class = "em-card-negative"

                time_value = row_left.get("Zeit")
                time_text = pd.to_datetime(time_value, errors="coerce").strftime("%d.%m.%Y %H:%M") if pd.notna(time_value) else "-"

                pnl_line = ""
                if pd.notna(realized):
                    pnl_line = f"<div class='em-card-sub'><strong>Realized PnL: {float(realized):.2f} €</strong></div>"

                st.markdown(
                    f"""
                    <div class="em-card {border_class}">
                        <div class="em-badge {badge_class}">{trade_type}</div>
                        <div class="em-card-title">{symbol}</div>
                        <div class="em-card-sub">Zeit: {time_text}</div>
                        <div class="em-card-sub">Stück: {pieces}</div>
                        <div class="em-card-sub">Preis: {price:.2f} €</div>
                        <div class="em-card-sub">Gebühr: {fee:.2f} €</div>
                        <div class="em-card-sub">Gesamt: {total_value:.2f} €</div>
                        {pnl_line}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            if i + 1 < len(recent_cards_df):
                row_right = recent_cards_df.iloc[i + 1]

                with col2:
                    trade_type = str(row_right.get("Typ", "-"))
                    symbol = str(row_right.get("Symbol", "-"))
                    fee = float(row_right.get("Gebühr", 0.0))
                    total_value = float(row_right.get("Gesamt", 0.0))
                    price = float(row_right.get("Preis", 0.0))
                    pieces = int(float(row_right.get("Stück", 0)))
                    realized = row_right.get("Realized PnL", None)

                    badge_class = "em-badge-buy" if trade_type.lower() == "kauf" else "em-badge-sell"
                    border_class = ""
                    if pd.notna(realized) and float(realized) > 0:
                        border_class = "em-card-positive"
                    elif pd.notna(realized) and float(realized) < 0:
                        border_class = "em-card-negative"

                    time_value = row_right.get("Zeit")
                    time_text = pd.to_datetime(time_value, errors="coerce").strftime("%d.%m.%Y %H:%M") if pd.notna(time_value) else "-"

                    pnl_line = ""
                    if pd.notna(realized):
                        pnl_line = f"<div class='em-card-sub'><strong>Realized PnL: {float(realized):.2f} €</strong></div>"

                    st.markdown(
                        f"""
                        <div class="em-card {border_class}">
                            <div class="em-badge {badge_class}">{trade_type}</div>
                            <div class="em-card-title">{symbol}</div>
                            <div class="em-card-sub">Zeit: {time_text}</div>
                            <div class="em-card-sub">Stück: {pieces}</div>
                            <div class="em-card-sub">Preis: {price:.2f} €</div>
                            <div class="em-card-sub">Gebühr: {fee:.2f} €</div>
                            <div class="em-card-sub">Gesamt: {total_value:.2f} €</div>
                            {pnl_line}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    with st.expander("📋 Vollständige Tabellenansicht", expanded=False):
        display_history_df = history_df.copy()

        if "Zeit" in display_history_df.columns:
            display_history_df["Zeit"] = pd.to_datetime(
                display_history_df["Zeit"], errors="coerce"
            ).dt.strftime("%d.%m.%Y %H:%M")

        st.dataframe(display_history_df, width="stretch")

def ensure_trade_journal_notes_store():
    if "trade_journal_notes" not in st.session_state:
        st.session_state.trade_journal_notes = {}


def build_trade_note_key(row: pd.Series, idx: int):
    zeit = str(row.get("Zeit", ""))
    symbol = str(row.get("Symbol", ""))
    trade_type = str(row.get("Typ", ""))
    order_type = str(row.get("Order", ""))
    return f"{idx}|{zeit}|{symbol}|{trade_type}|{order_type}"


def get_trade_note_payload(note_key: str):
    ensure_trade_journal_notes_store()
    default_payload = {
        "setup_quality": "Nicht bewertet",
        "mistake_tag": "Kein Fehler",
        "emotion_tag": "Neutral",
        "lesson_note": "",
        "plan_followed": "Unbekannt"
    }
    return st.session_state.trade_journal_notes.get(note_key, default_payload.copy())


def save_trade_note_payload(note_key: str, payload: dict):
    ensure_trade_journal_notes_store()
    st.session_state.trade_journal_notes[note_key] = payload
    save_trade_journal_notes(st.session_state.trade_journal_notes)


def build_trade_notes_dataframe(review_df: pd.DataFrame):
    ensure_trade_journal_notes_store()

    if review_df.empty:
        return pd.DataFrame()

    rows = []
    for idx, row in review_df.reset_index(drop=True).iterrows():
        note_key = build_trade_note_key(row, idx)
        payload = get_trade_note_payload(note_key)

        rows.append({
            "Trade Key": note_key,
            "Zeit": row.get("Zeit"),
            "Symbol": row.get("Symbol"),
            "Typ": row.get("Typ"),
            "Order": row.get("Order"),
            "Realized PnL": row.get("Realized PnL"),
            "Setup Quality": payload.get("setup_quality", "Nicht bewertet"),
            "Mistake Tag": payload.get("mistake_tag", "Kein Fehler"),
            "Emotion Tag": payload.get("emotion_tag", "Neutral"),
            "Plan Followed": payload.get("plan_followed", "Unbekannt"),
            "Lesson Note": payload.get("lesson_note", ""),
        })

    df = pd.DataFrame(rows)
    if "Zeit" in df.columns:
        df["Zeit"] = pd.to_datetime(df["Zeit"], errors="coerce")
    return df


def calculate_journal_learning_metrics(notes_df: pd.DataFrame):
    if notes_df.empty:
        return {
            "rated_trades": 0,
            "good_setups": 0,
            "mistake_trades": 0,
            "plan_follow_rate": 0.0,
            "most_common_mistake": "-",
            "most_common_emotion": "-"
        }

    rated_trades = int((notes_df["Setup Quality"] != "Nicht bewertet").sum())
    good_setups = int(notes_df["Setup Quality"].isin(["Gut", "Sehr gut"]).sum())
    mistake_trades = int((notes_df["Mistake Tag"] != "Kein Fehler").sum())

    known_plan = notes_df[notes_df["Plan Followed"].isin(["Ja", "Nein"])].copy()
    plan_follow_rate = float((known_plan["Plan Followed"] == "Ja").mean() * 100) if not known_plan.empty else 0.0

    mistake_counts = notes_df["Mistake Tag"].value_counts(dropna=False)
    most_common_mistake = "-"
    if not mistake_counts.empty:
        candidate = str(mistake_counts.index[0])
        most_common_mistake = candidate if candidate else "-"

    emotion_counts = notes_df["Emotion Tag"].value_counts(dropna=False)
    most_common_emotion = "-"
    if not emotion_counts.empty:
        candidate = str(emotion_counts.index[0])
        most_common_emotion = candidate if candidate else "-"

    return {
        "rated_trades": rated_trades,
        "good_setups": good_setups,
        "mistake_trades": mistake_trades,
        "plan_follow_rate": plan_follow_rate,
        "most_common_mistake": most_common_mistake,
        "most_common_emotion": most_common_emotion
    }


def render_learning_metrics(metrics: dict):
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Bewertete Trades", metrics["rated_trades"])

    with c2:
        st.metric("Gute Setups", metrics["good_setups"])

    with c3:
        st.metric("Trades mit Fehler", metrics["mistake_trades"])

    with c4:
        st.metric("Plan befolgt", f"{metrics['plan_follow_rate']:.2f}%")

    c5, c6 = st.columns(2)

    with c5:
        st.markdown(
            f"""
            <div class="em-card">
                <div class="em-card-title">Häufigster Fehler</div>
                <div class="em-card-sub">{metrics['most_common_mistake']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c6:
        st.markdown(
            f"""
            <div class="em-card">
                <div class="em-card-title">Häufigste Emotion</div>
                <div class="em-card-sub">{metrics['most_common_emotion']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )


def build_learning_feedback(notes_df: pd.DataFrame, metrics: dict):
    feedback = []

    if notes_df.empty:
        return ["Noch keine Review-Notizen vorhanden. Sobald du Trades bewertest, bekommst du hier Lernhinweise."]

    if metrics["plan_follow_rate"] >= 70:
        feedback.append("Du hältst dich oft an deinen Plan. Das ist für langfristige Konstanz ein sehr gutes Zeichen.")
    elif 0 < metrics["plan_follow_rate"] < 50:
        feedback.append("Du weichst noch oft von deinem Plan ab. Gerade das ist oft eine der größten Fehlerquellen.")

    if metrics["mistake_trades"] >= max(3, metrics["rated_trades"] * 0.4):
        feedback.append("Viele bewertete Trades enthalten Fehler-Tags. Schau dir an, welche Fehler immer wieder auftauchen.")

    if metrics["most_common_mistake"] == "Zu früher Einstieg":
        feedback.append("Dein häufigster Fehler ist ein zu früher Einstieg. Mehr Geduld am Entry könnte deine Qualität stark verbessern.")
    elif metrics["most_common_mistake"] == "Zu später Einstieg":
        feedback.append("Du steigst häufig spät ein. Prüfe, ob du Bewegungen hinterherläufst statt auf saubere Setups zu warten.")
    elif metrics["most_common_mistake"] == "SL verschoben":
        feedback.append("Das Verschieben des Stop-Loss taucht öfter auf. Das ist oft ein Zeichen für emotionale Entscheidungen.")
    elif metrics["most_common_mistake"] == "Kein klarer Plan":
        feedback.append("Mehrere Trades hatten keinen klaren Plan. Versuche vor jedem Entry Setup, Risiko und Ziel festzuhalten.")

    if metrics["most_common_emotion"] == "FOMO":
        feedback.append("FOMO taucht häufig auf. Das spricht oft für zu späte Entries oder impulsive Entscheidungen.")
    elif metrics["most_common_emotion"] == "Angst":
        feedback.append("Angst taucht in deinen Reviews häufig auf. Vielleicht ist deine Positionsgröße noch zu groß.")
    elif metrics["most_common_emotion"] == "Gier":
        feedback.append("Gier kommt öfter vor. Das kann bedeuten, dass Gewinne zu lange gehalten oder Ziele zu weit gesetzt werden.")

    if not feedback:
        feedback.append("Deine Reviews wirken schon recht strukturiert. Jetzt lohnt es sich, die Qualität deiner Setups weiter zu vergleichen.")

    return feedback


def render_learning_feedback(feedback_lines: list):
    for line in feedback_lines:
        st.markdown(
            f"""
            <div class="em-card">
                <div class="em-card-title">Lernfortschritt</div>
                <div class="em-card-sub">{line}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

def build_learning_dashboard_counts(notes_df: pd.DataFrame):
    if notes_df.empty:
        return {
            "mistake_counts": pd.Series(dtype="int64"),
            "emotion_counts": pd.Series(dtype="int64"),
            "setup_counts": pd.Series(dtype="int64"),
            "plan_counts": pd.Series(dtype="int64"),
        }

    return {
        "mistake_counts": notes_df["Mistake Tag"].fillna("Unbekannt").value_counts(),
        "emotion_counts": notes_df["Emotion Tag"].fillna("Unbekannt").value_counts(),
        "setup_counts": notes_df["Setup Quality"].fillna("Unbekannt").value_counts(),
        "plan_counts": notes_df["Plan Followed"].fillna("Unbekannt").value_counts(),
    }


def create_learning_bar_figure(series: pd.Series, title: str, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    fig = go.Figure()

    if not series.empty:
        fig.add_trace(
            go.Bar(
                x=series.index.astype(str),
                y=series.values,
                name=title
            )
        )

    fig.update_layout(
        template=colors["template"],
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="Kategorie",
        yaxis_title="Anzahl",
        showlegend=False,
        title=title
    )

    fig.update_xaxes(gridcolor="rgba(120,180,255,0.08)")
    fig.update_yaxes(gridcolor="rgba(120,180,255,0.08)")

    return fig


def create_setup_vs_pnl_figure(notes_df: pd.DataFrame, review_df: pd.DataFrame, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    if notes_df.empty:
        fig = go.Figure()
        fig.update_layout(
            template=colors["template"],
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=colors["font_color"]),
            margin=dict(l=20, r=20, t=40, b=20),
            title="Setup-Qualität vs. Ø PnL"
        )
        return fig

    working_df = notes_df.copy()

    if "Realized PnL" not in working_df.columns and not review_df.empty and "Realized PnL" in review_df.columns:
        working_df = working_df.merge(
            review_df[["Zeit", "Symbol", "Order", "Realized PnL"]],
            on=["Zeit", "Symbol", "Order"],
            how="left"
        )

    if "Realized PnL" not in working_df.columns:
        working_df["Realized PnL"] = 0.0

    grouped = working_df.groupby("Setup Quality", dropna=False)["Realized PnL"].mean().sort_values(ascending=False)

    fig = go.Figure()

    if not grouped.empty:
        fig.add_trace(
            go.Bar(
                x=grouped.index.astype(str),
                y=grouped.values,
                name="Ø PnL je Setup"
            )
        )

    fig.update_layout(
        template=colors["template"],
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="Setup-Qualität",
        yaxis_title="Ø Realized PnL (€)",
        showlegend=False,
        title="Setup-Qualität vs. Ø PnL"
    )

    fig.update_xaxes(gridcolor="rgba(120,180,255,0.08)")
    fig.update_yaxes(gridcolor="rgba(120,180,255,0.08)")

    return fig


def create_cumulative_realized_pnl_figure(review_df: pd.DataFrame, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    fig = go.Figure()

    if not review_df.empty:
        cumulative_df = review_df.copy().sort_values("Zeit")
        cumulative_df["CumPnL"] = cumulative_df["Realized PnL"].fillna(0).cumsum()

        fig.add_trace(
            go.Scatter(
                x=cumulative_df["Zeit"],
                y=cumulative_df["CumPnL"],
                mode="lines+markers",
                name="Kumulativer PnL"
            )
        )

    fig.update_layout(
        template=colors["template"],
        height=340,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="Zeit",
        yaxis_title="Kumulativer PnL (€)",
        showlegend=False,
        title="Kumulativer Realized PnL"
    )

    fig.update_xaxes(gridcolor="rgba(120,180,255,0.08)")
    fig.update_yaxes(gridcolor="rgba(120,180,255,0.08)")

    return fig


def build_learning_dashboard_highlights(notes_df: pd.DataFrame, review_df: pd.DataFrame):
    highlights = []

    if notes_df.empty:
        return ["Noch nicht genug Journal-Daten für das Learning Dashboard."]

    mistake_counts = notes_df["Mistake Tag"].fillna("Unbekannt").value_counts()
    emotion_counts = notes_df["Emotion Tag"].fillna("Unbekannt").value_counts()

    if not mistake_counts.empty:
        top_mistake = str(mistake_counts.index[0])
        if top_mistake != "Kein Fehler":
            highlights.append(f"Dein häufigster Fehler ist aktuell: **{top_mistake}**.")

    if not emotion_counts.empty:
        top_emotion = str(emotion_counts.index[0])
        highlights.append(f"Deine häufigste Emotion im Review ist: **{top_emotion}**.")

    if "Setup Quality" in notes_df.columns and "Realized PnL" in notes_df.columns:
        setup_group = notes_df.groupby("Setup Quality", dropna=False)["Realized PnL"].mean().sort_values(ascending=False)
        if not setup_group.empty:
            best_setup = str(setup_group.index[0])
            highlights.append(f"Die aktuell beste bewertete Setup-Kategorie nach Ø PnL ist: **{best_setup}**.")

    if not review_df.empty:
        wins = int((review_df["Realized PnL"] > 0).sum())
        losses = int((review_df["Realized PnL"] < 0).sum())
        if wins > losses:
            highlights.append("Aktuell überwiegen deine Gewinntrades gegenüber den Verlusttrades.")
        elif losses > wins:
            highlights.append("Aktuell überwiegen deine Verlusttrades. Vielleicht lohnt sich ein engerer Fokus auf saubere Setups.")

    if not highlights:
        highlights.append("Das Dashboard sammelt bereits erste Muster. Mit mehr Reviews werden die Aussagen noch hilfreicher.")

    return highlights


def render_learning_dashboard_highlights(highlights: list):
    for line in highlights:
        st.markdown(
            f"""
            <div class="em-card">
                <div class="em-card-title">Learning Insight</div>
                <div class="em-card-sub">{line}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

def build_watchlist_metrics(data: pd.DataFrame):
    if data is None or data.empty:
        return {}

    latest = data.iloc[-1]

    price = float(latest["Close"])
    prev = float(data["Close"].iloc[-2]) if len(data) > 1 else price

    change_pct = ((price - prev) / prev * 100) if prev != 0 else 0

    rsi = float(latest.get("RSI", 0))
    ema20 = float(latest.get("EMA20", price))
    ema50 = float(latest.get("EMA50", price))

    trend = "Neutral"
    if price > ema20 > ema50:
        trend = "Bullisch"
    elif price < ema20 < ema50:
        trend = "Bearisch"

    return {
        "price": price,
        "change_pct": change_pct,
        "rsi": rsi,
        "trend": trend
    }


def classify_symbol(metrics):
    if not metrics:
        return "Unbekannt"

    if metrics["rsi"] > 70:
        return "Überkauft"

    if metrics["rsi"] < 30:
        return "Überverkauft"

    if metrics["trend"] == "Bullisch":
        return "Trend Long"

    if metrics["trend"] == "Bearisch":
        return "Trend Schwach"

    return "Neutral"

def detect_symbol_alerts(symbol: str, data: pd.DataFrame, supports: list | None = None, resistances: list | None = None):
    if data is None or data.empty or len(data) < 2:
        return []

    latest = data.iloc[-1]
    prev = data.iloc[-2]

    price = float(latest["Close"])
    prev_price = float(prev["Close"])

    rsi = float(latest.get("RSI", 50.0))
    prev_rsi = float(prev.get("RSI", 50.0))

    ema20 = float(latest.get("EMA20", price))
    ema50 = float(latest.get("EMA50", price))
    prev_ema20 = float(prev.get("EMA20", prev_price))
    prev_ema50 = float(prev.get("EMA50", prev_price))

    alerts = []

    # RSI
    if rsi >= 70 and prev_rsi < 70:
        alerts.append({
            "Symbol": symbol,
            "Kategorie": "RSI",
            "Signal": "Markt wirkt überhitzt",
            "Detail": f"RSI ist auf {rsi:.2f} gestiegen.",
            "Priorität": "Mittel"
        })

    if rsi <= 30 and prev_rsi > 30:
        alerts.append({
            "Symbol": symbol,
            "Kategorie": "RSI",
            "Signal": "Markt wirkt stark gefallen",
            "Detail": f"RSI ist auf {rsi:.2f} gefallen.",
            "Priorität": "Mittel"
        })

    # EMA Cross
    if prev_ema20 <= prev_ema50 and ema20 > ema50:
        alerts.append({
            "Symbol": symbol,
            "Kategorie": "Trend",
            "Signal": "Mögliches Trend-Signal nach oben",
            "Detail": "EMA20 hat EMA50 nach oben gekreuzt.",
            "Priorität": "Hoch"
        })

    if prev_ema20 >= prev_ema50 and ema20 < ema50:
        alerts.append({
            "Symbol": symbol,
            "Kategorie": "Trend",
            "Signal": "Mögliches Trend-Signal nach unten",
            "Detail": "EMA20 hat EMA50 nach unten gekreuzt.",
            "Priorität": "Hoch"
        })

    # Preis vs EMA20
    if prev_price <= prev_ema20 and price > ema20:
        alerts.append({
            "Symbol": symbol,
            "Kategorie": "Trend",
            "Signal": "Preis zieht über EMA20",
            "Detail": "Möglicher kurzfristiger Stärkewechsel.",
            "Priorität": "Niedrig"
        })

    if prev_price >= prev_ema20 and price < ema20:
        alerts.append({
            "Symbol": symbol,
            "Kategorie": "Trend",
            "Signal": "Preis fällt unter EMA20",
            "Detail": "Möglicher kurzfristiger Schwächewechsel.",
            "Priorität": "Niedrig"
        })

    # Starker Trend-Kandidat
    if price > ema20 > ema50 and 45 <= rsi <= 68:
        alerts.append({
            "Symbol": symbol,
            "Kategorie": "Setup",
            "Signal": "Trend-Long-Kandidat",
            "Detail": "Preis liegt über EMA20 und EMA50, RSI bleibt noch im moderaten Bereich.",
            "Priorität": "Hoch"
        })

    # Support / Resistance Nähe (optional)
    if supports:
        nearest_support = max([s for s in supports if s < price], default=None)
        if nearest_support is not None:
            dist_support = abs(price - nearest_support) / price * 100 if price > 0 else 999
            if dist_support <= 1.0:
                alerts.append({
                    "Symbol": symbol,
                    "Kategorie": "Zone",
                    "Signal": "Nahe an Support",
                    "Detail": f"Preis ist nur {dist_support:.2f}% vom Support entfernt.",
                    "Priorität": "Mittel"
                })

    if resistances:
        nearest_resistance = min([r for r in resistances if r > price], default=None)
        if nearest_resistance is not None:
            dist_res = abs(nearest_resistance - price) / price * 100 if price > 0 else 999
            if dist_res <= 1.0:
                alerts.append({
                    "Symbol": symbol,
                    "Kategorie": "Zone",
                    "Signal": "Nahe an Resistance",
                    "Detail": f"Preis ist nur {dist_res:.2f}% von der Resistance entfernt.",
                    "Priorität": "Mittel"
                })

    return alerts


def build_watchlist_alerts(symbols: list, period: str, interval: str):
    all_alerts = []

    for symbol in symbols:
        try:
            symbol_data = load_data(symbol, period=period, interval=interval)
            if symbol_data.empty:
                continue

            symbol_data = calculate_indicators(symbol_data)
            alerts = detect_symbol_alerts(symbol, symbol_data)
            all_alerts.extend(alerts)
        except Exception:
            continue

    return pd.DataFrame(all_alerts)


def render_alert_card(alert_row: dict, idx: int):
    priority = str(alert_row.get("Priorität", "Niedrig"))
    border_class = ""
    if priority == "Hoch":
        border_class = "em-card-positive"
    elif priority == "Mittel":
        border_class = ""

    st.markdown(
        f"""
        <div class="em-card {border_class}">
            <div class="em-card-title">{alert_row.get("Symbol", "-")} – {alert_row.get("Signal", "-")}</div>
            <div class="em-card-sub">Kategorie: {alert_row.get("Kategorie", "-")}</div>
            <div class="em-card-sub">Priorität: {priority}</div>
            <div class="em-card-sub">{alert_row.get("Detail", "")}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("In Analyse öffnen", key=f"alert_open_analysis_{idx}", width="stretch"):
            st.session_state.ticker = str(alert_row.get("Symbol", st.session_state.ticker))
            st.success(f"{st.session_state.ticker} wurde für die Analyse gewählt.")
            st.rerun()

    with col2:
        if st.button("Für Paper Trading wählen", key=f"alert_open_paper_{idx}", width="stretch"):
            st.session_state.ticker = str(alert_row.get("Symbol", st.session_state.ticker))
            st.success(f"{st.session_state.ticker} wurde für Paper Trading gewählt.")
            st.rerun()


def render_signal_center(alerts_df: pd.DataFrame):
    st.write("### Signal Center")
    st.caption("Hier siehst du automatisch erkannte Marktsituationen aus deiner Watchlist.")

    if alerts_df.empty:
        st.info("Aktuell keine neuen Signale in der Watchlist gefunden.")
        return

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        category_filter = st.selectbox(
            "Kategorie",
            ["Alle"] + sorted(alerts_df["Kategorie"].dropna().astype(str).unique().tolist()),
            key="signal_center_category_filter"
        )

    with filter_col2:
        priority_filter = st.selectbox(
            "Priorität",
            ["Alle", "Hoch", "Mittel", "Niedrig"],
            key="signal_center_priority_filter"
        )

    filtered_alerts = alerts_df.copy()

    if category_filter != "Alle":
        filtered_alerts = filtered_alerts[filtered_alerts["Kategorie"].astype(str) == category_filter]

    if priority_filter != "Alle":
        filtered_alerts = filtered_alerts[filtered_alerts["Priorität"].astype(str) == priority_filter]

    if filtered_alerts.empty:
        st.info("Für diese Filter gibt es aktuell keine Signale.")
        return

    for idx, row in filtered_alerts.reset_index(drop=True).iterrows():
        render_alert_card(row.to_dict(), idx)

    with st.expander("📋 Tabellenansicht Signal Center", expanded=False):
        st.dataframe(filtered_alerts, width="stretch")

def render_hero(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="em-hero">
            <div class="em-hero-title">{title}</div>
            <div class="em-hero-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def section_header(title: str, caption: str | None = None):
    st.markdown(f'<div class="em-section-title">{title}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="em-section-caption">{caption}</div>', unsafe_allow_html=True)


def panel_note(title: str, subtitle: str | None = None):
    subtitle_html = f'<div class="em-panel-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="em-panel">
            <div class="em-panel-title">{title}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def ui_gap(size: str = "md"):
    allowed = {"sm", "md", "lg"}
    size = size if size in allowed else "md"
    st.markdown(f'<div class="em-gap-{size}"></div>', unsafe_allow_html=True)

def render_help_center():

    with st.expander("📘 Hilfe & Einstieg", expanded=False):

        st.markdown("### 🚀 So startest du")
        st.write("""
        1. Wähle ein Symbol (z. B. TSLA, BTC-USD)
        2. Schau dir den Analyse-Tab an
        3. Nutze die Trade-Idee als Orientierung
        4. Teste deine Idee im Paper Trading
        """)

        st.markdown("### 📊 Was bedeuten die wichtigsten Begriffe?")
        st.write("""
        **EMA** → zeigt den Trend (steigend = Aufwärtstrend)  
        **RSI** → zeigt, ob ein Markt eher überkauft oder überverkauft ist  
        **MACD** → hilft Trendwechsel zu erkennen  
        **Support / Resistance** → wichtige Preiszonen  
        **Stop-Loss (SL)** → begrenzt deinen Verlust  
        **Take-Profit (TP)** → sichert deinen Gewinn  
        """)

        st.markdown("### 🧠 Tipps für Anfänger")
        st.write("""
        - Handle erstmal nur mit Paper Trading  
        - Nutze Stop-Loss immer  
        - Fokus auf wenige Märkte  
        - Nicht zu viele Indikatoren gleichzeitig  
        """)

def help_text(text):
    return f"{text}"

def render_context_hint(title, text):
    st.markdown(f"""
    <div class="em-panel">
        <div class="em-panel-title">{title}</div>
        <div class="em-panel-sub">{text}</div>
    </div>
    """, unsafe_allow_html=True)

import json
from datetime import datetime


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    if df is None:
        df = pd.DataFrame()
    export_df = df.copy()
    return export_df.to_csv(index=False).encode("utf-8")


def dict_to_json_bytes(payload: dict) -> bytes:
    if payload is None:
        payload = {}
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def build_export_trade_history_df():
    if not st.session_state.get("paper_history"):
        return pd.DataFrame()

    df = pd.DataFrame(st.session_state.paper_history).copy()

    if "Zeit" in df.columns:
        df["Zeit"] = pd.to_datetime(df["Zeit"], errors="coerce")

    return df.sort_values("Zeit", ascending=False).reset_index(drop=True)


def build_export_watchlist_df():
    watchlist = st.session_state.get("watchlist", [])
    return pd.DataFrame({"Symbol": watchlist})


def build_export_journal_notes_df():
    notes = st.session_state.get("trade_journal_notes", {})
    if not notes:
        return pd.DataFrame()

    rows = []
    for note_key, payload in notes.items():
        row = {"Trade Key": note_key}
        if isinstance(payload, dict):
            row.update(payload)
        rows.append(row)

    return pd.DataFrame(rows)


def build_export_settings_dict():
    return {
        "ticker": st.session_state.get("ticker"),
        "symbol_mode": st.session_state.get("symbol_mode"),
        "compare_input": st.session_state.get("compare_input_clean", st.session_state.get("compare_input")),
        "period": st.session_state.get("period"),
        "interval": st.session_state.get("interval"),
        "chart_theme": st.session_state.get("chart_theme"),
        "show_onboarding": st.session_state.get("show_onboarding"),
        "fee_percent": st.session_state.get("fee_percent"),
        "stop_loss_percent": st.session_state.get("stop_loss_percent"),
        "take_profit_percent": st.session_state.get("take_profit_percent"),
        "trailing_stop_percent": st.session_state.get("trailing_stop_percent"),
        "use_rsi_filter": st.session_state.get("use_rsi_filter"),
        "rsi_min": st.session_state.get("rsi_min"),
        "rsi_max": st.session_state.get("rsi_max"),
        "use_ema200_filter": st.session_state.get("use_ema200_filter"),
        "paper_cash": st.session_state.get("paper_cash"),
    }


def build_full_backup_dict():
    return {
        "created_at": datetime.now().isoformat(),
        "settings": build_export_settings_dict(),
        "watchlist": st.session_state.get("watchlist", []),
        "paper_history": st.session_state.get("paper_history", []),
        "paper_positions": st.session_state.get("paper_positions", {}),
        "paper_open_orders": st.session_state.get("paper_open_orders", []),
        "paper_equity_history": st.session_state.get("paper_equity_history", []),
        "trade_journal_notes": st.session_state.get("trade_journal_notes", {}),
    }

import json


def parse_uploaded_backup_json(uploaded_file):
    if uploaded_file is None:
        return None, "Keine Datei hochgeladen."

    try:
        raw_bytes = uploaded_file.read()
        parsed = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(parsed, dict):
            return None, "Die Datei enthält kein gültiges Backup-Objekt."
        return parsed, None
    except Exception as e:
        return None, f"Backup konnte nicht gelesen werden: {e}"


def sanitize_watchlist_payload(payload):
    if not isinstance(payload, list):
        return []
    cleaned = []
    for item in payload:
        symbol = str(item).upper().strip()
        if symbol and symbol not in cleaned:
            cleaned.append(symbol)
    return cleaned


def sanitize_dict_payload(payload):
    return payload if isinstance(payload, dict) else {}


def sanitize_list_payload(payload):
    return payload if isinstance(payload, list) else []


def restore_backup_sections(
    backup_data: dict,
    restore_settings: bool,
    restore_watchlist: bool,
    restore_journal: bool,
    restore_paper_data: bool
):
    restored_parts = []

    if restore_settings:
        settings = sanitize_dict_payload(backup_data.get("settings", {}))
        for key, value in settings.items():
            st.session_state[key] = value
        restored_parts.append("Settings")

    if restore_watchlist:
        restored_watchlist = sanitize_watchlist_payload(backup_data.get("watchlist", []))
        st.session_state.watchlist = restored_watchlist
        restored_parts.append("Watchlist")

    if restore_journal:
        restored_notes = sanitize_dict_payload(backup_data.get("trade_journal_notes", {}))
        st.session_state.trade_journal_notes = restored_notes
        if "save_trade_journal_notes" in globals():
            try:
                save_trade_journal_notes(restored_notes)
            except Exception:
                pass
        restored_parts.append("Journal-Notizen")

    if restore_paper_data:
        st.session_state.paper_history = sanitize_list_payload(backup_data.get("paper_history", []))
        st.session_state.paper_open_orders = sanitize_list_payload(backup_data.get("paper_open_orders", []))
        st.session_state.paper_equity_history = sanitize_list_payload(backup_data.get("paper_equity_history", []))
        st.session_state.paper_positions = sanitize_dict_payload(backup_data.get("paper_positions", {}))

        paper_cash = backup_data.get("paper_cash", None)
        if paper_cash is None:
            paper_cash = sanitize_dict_payload(backup_data.get("settings", {})).get("paper_cash", st.session_state.get("paper_cash", 10000.0))
        try:
            st.session_state.paper_cash = float(paper_cash)
        except Exception:
            pass

        restored_parts.append("Paper-Trading-Daten")

    return restored_parts


def build_backup_preview_lines(backup_data: dict):
    preview = []

    if "created_at" in backup_data:
        preview.append(f"Erstellt am: {backup_data.get('created_at')}")

    watchlist = backup_data.get("watchlist", [])
    if isinstance(watchlist, list):
        preview.append(f"Watchlist Symbole: {len(watchlist)}")

    paper_history = backup_data.get("paper_history", [])
    if isinstance(paper_history, list):
        preview.append(f"Trades in Historie: {len(paper_history)}")

    journal_notes = backup_data.get("trade_journal_notes", {})
    if isinstance(journal_notes, dict):
        preview.append(f"Journal-Notizen: {len(journal_notes)}")

    settings = backup_data.get("settings", {})
    if isinstance(settings, dict) and settings:
        preview.append(f"Settings-Felder: {len(settings)}")

    return preview

def reset_watchlist_data():
    st.session_state.watchlist = []
    try:
        save_watchlist(st.session_state.watchlist)
    except Exception:
        pass


def reset_journal_data():
    st.session_state.trade_journal_notes = {}
    if "save_trade_journal_notes" in globals():
        try:
            save_trade_journal_notes({})
        except Exception:
            pass


def reset_paper_trading_data():
    st.session_state.paper_cash = 10000.0
    st.session_state.paper_positions = {}
    st.session_state.paper_history = []
    st.session_state.paper_open_orders = []
    st.session_state.paper_equity_history = []
    st.session_state.paper_trade_idea = None
    st.session_state.trade_idea_prefill_sl = None
    st.session_state.trade_idea_prefill_tp = None


def reset_settings_data():
    keys_to_reset = {
        "ticker": "TSLA",
        "symbol_mode": "Watchlist",
        "compare_input": "TSLA, AAPL, NVDA",
        "period": "3mo",
        "interval": "1d",
        "chart_theme": "Dark",
        "show_onboarding": True,
        "fee_percent": 0.1,
        "stop_loss_percent": 2.0,
        "take_profit_percent": 4.0,
        "trailing_stop_percent": 1.5,
        "use_rsi_filter": False,
        "rsi_min": 30.0,
        "rsi_max": 70.0,
        "use_ema200_filter": False,
        "show_trade_markers": True,
        "show_ema": True,
        "show_fibonacci": True,
        "show_support_resistance": True,
        "show_volume": True,
        "show_paper_markers": True,
        "show_sl_tp_orders": True,
    }

    for key, value in keys_to_reset.items():
        st.session_state[key] = value

    if "save_user_settings" in globals():
        try:
            save_user_settings(build_export_settings_dict() if "build_export_settings_dict" in globals() else {})
        except Exception:
            pass


def reset_all_app_data():
    reset_watchlist_data()
    reset_journal_data()
    reset_paper_trading_data()
    reset_settings_data()

def build_release_check_results():
    checks = []

    watchlist = st.session_state.get("watchlist", [])
    paper_positions = st.session_state.get("paper_positions", {})
    paper_orders = st.session_state.get("paper_open_orders", [])
    paper_history = st.session_state.get("paper_history", [])
    journal_notes = st.session_state.get("trade_journal_notes", {})
    ticker = st.session_state.get("ticker", "")
    paper_cash = float(st.session_state.get("paper_cash", 0.0))

    checks.append({
        "title": "Watchlist vorhanden",
        "status": len(watchlist) > 0,
        "detail": f"Aktuell {len(watchlist)} Symbol(e) in der Watchlist."
    })

    checks.append({
        "title": "Aktives Symbol gesetzt",
        "status": bool(str(ticker).strip()),
        "detail": f"Aktuelles Symbol: {ticker if str(ticker).strip() else '-'}"
    })

    checks.append({
        "title": "Paper Cash positiv",
        "status": paper_cash >= 0,
        "detail": f"Paper Cash: {paper_cash:.2f} €"
    })

    checks.append({
        "title": "Trade Historie vorhanden",
        "status": len(paper_history) > 0,
        "detail": f"{len(paper_history)} Historien-Einträge vorhanden."
    })

    checks.append({
        "title": "Journal-Notizen vorhanden",
        "status": len(journal_notes) > 0,
        "detail": f"{len(journal_notes)} Journal-Notiz(en) vorhanden."
    })

    invalid_orders = []
    for order in paper_orders:
        symbol = order.get("Symbol")
        order_type = order.get("Order Type")
        qty = float(order.get("Stück", 0))

        if not symbol or qty <= 0:
            invalid_orders.append(order)
            continue

        if order_type in ["Stop-Loss", "Take-Profit", "Trailing"] and symbol not in paper_positions:
            invalid_orders.append(order)

    checks.append({
        "title": "Keine verwaisten Orders",
        "status": len(invalid_orders) == 0,
        "detail": f"{len(invalid_orders)} problematische Order(s) gefunden."
    })

    return checks


def render_release_check_cards(checks: list):
    for check in checks:
        border_class = "em-card-positive" if check["status"] else "em-card-negative"
        icon = "✅" if check["status"] else "⚠️"

        st.markdown(
            f"""
            <div class="em-card {border_class}">
                <div class="em-card-title">{icon} {check['title']}</div>
                <div class="em-card-sub">{check['detail']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )


def build_release_summary(checks: list):
    passed = sum(1 for c in checks if c["status"])
    total = len(checks)
    return passed, total


def get_release_feedback(checks: list):
    feedback = []

    failed_titles = [c["title"] for c in checks if not c["status"]]

    if not failed_titles:
        feedback.append("Die wichtigsten Grundchecks sehen gut aus. Die App wirkt stabil und einsatzbereit.")
        return feedback

    if "Watchlist vorhanden" in failed_titles:
        feedback.append("Deine Watchlist ist leer. Für Scanner und Signale solltest du mindestens ein paar Symbole hinzufügen.")

    if "Trade Historie vorhanden" in failed_titles:
        feedback.append("Noch keine Trade-Historie vorhanden. Einige Review- und Journal-Bereiche werden erst mit Trades sinnvoll.")

    if "Journal-Notizen vorhanden" in failed_titles:
        feedback.append("Es gibt noch keine Journal-Notizen. Für das Learning Dashboard ist das sehr hilfreich.")

    if "Keine verwaisten Orders" in failed_titles:
        feedback.append("Es gibt offene Orders ohne passende Position. Ein kurzer Cleanup oder Reset der Orders kann helfen.")

    if "Paper Cash positiv" in failed_titles:
        feedback.append("Dein Paper Cash ist negativ. Das solltest du prüfen oder die Paper-Trading-Daten zurücksetzen.")

    return feedback


def render_release_feedback(feedback_lines: list):
    for line in feedback_lines:
        panel_note("Release-Hinweis", line)

def calculate_quantity_from_risk_amount(entry_price: float, stop_loss_price: float, risk_amount: float) -> int:
    try:
        entry_price = float(entry_price)
        stop_loss_price = float(stop_loss_price)
        risk_amount = float(risk_amount)
    except Exception:
        return 0

    if entry_price <= 0 or stop_loss_price <= 0 or risk_amount <= 0:
        return 0

    risk_per_share = entry_price - stop_loss_price

    if risk_per_share <= 0:
        return 0

    quantity = int(risk_amount / risk_per_share)
    return max(0, quantity)


def calculate_position_value(entry_price: float, quantity: int) -> float:
    try:
        return float(entry_price) * int(quantity)
    except Exception:
        return 0.0


def calculate_account_risk_percent(risk_amount: float, account_size: float) -> float:
    try:
        risk_amount = float(risk_amount)
        account_size = float(account_size)
    except Exception:
        return 0.0

    if account_size <= 0:
        return 0.0

    return (risk_amount / account_size) * 100


def get_position_sizing_summary(entry_price: float, stop_loss_price: float, quantity: int, account_size: float):
    total_position_value = calculate_position_value(entry_price, quantity)
    total_risk, risk_pct_price = calculate_trade_risk(entry_price, stop_loss_price, quantity)

    account_risk_pct = 0.0
    if total_risk is not None:
        account_risk_pct = calculate_account_risk_percent(total_risk, account_size)

    return {
        "position_value": total_position_value,
        "trade_risk_eur": total_risk if total_risk is not None else 0.0,
        "trade_risk_pct_price": risk_pct_price if risk_pct_price is not None else 0.0,
        "account_risk_pct": account_risk_pct
    }

def get_risk_profile_map():
    return {
        "Konservativ": {
            "risk_pct": 0.5,
            "description": "Kleines Risiko pro Trade. Gut für vorsichtiges Lernen."
        },
        "Moderat": {
            "risk_pct": 1.0,
            "description": "Ausgewogenes Risiko. Für die meisten Nutzer ein guter Standard."
        },
        "Aggressiv": {
            "risk_pct": 2.0,
            "description": "Höheres Risiko pro Trade. Nur sinnvoll, wenn du bewusst offensiver testen willst."
        },
    }


def calculate_risk_amount_from_profile(account_size: float, risk_percent: float) -> float:
    try:
        account_size = float(account_size)
        risk_percent = float(risk_percent)
    except Exception:
        return 0.0

    if account_size <= 0 or risk_percent <= 0:
        return 0.0

    return account_size * (risk_percent / 100.0)


def apply_risk_profile_to_session(profile_name: str):
    profiles = get_risk_profile_map()

    if profile_name not in profiles:
        return

    risk_pct = float(profiles[profile_name]["risk_pct"])
    risk_eur = calculate_risk_amount_from_profile(
        account_size=float(st.session_state.paper_cash),
        risk_percent=risk_pct
    )

    st.session_state.paper_risk_profile_v1 = profile_name
    st.session_state.paper_trade_risk_percent_v1 = risk_pct
    st.session_state.paper_trade_risk_eur_v1 = round(risk_eur, 2)


def render_risk_profile_panel():
    profiles = get_risk_profile_map()

    section_header(
        "Risiko-Profil",
        "Wähle ein Profil, damit die App ein sinnvolles Risiko pro Trade für dich vorbelegt."
    )

    profile_names = list(profiles.keys())

    selected_profile = st.selectbox(
        "Risiko-Profil wählen",
        profile_names,
        index=profile_names.index(st.session_state.paper_risk_profile_v1)
        if st.session_state.paper_risk_profile_v1 in profile_names else 1,
        key="paper_risk_profile_selector_v1",
        help="Das Profil legt fest, wie viel Prozent deines Paper-Kontos pro Trade riskiert werden."
    )

    profile_info = profiles[selected_profile]
    profile_risk_pct = float(profile_info["risk_pct"])
    profile_risk_eur = calculate_risk_amount_from_profile(
        account_size=float(st.session_state.paper_cash),
        risk_percent=profile_risk_pct
    )

    panel_note(
        selected_profile,
        f"{profile_info['description']} Aktuell wären das ca. {profile_risk_eur:.2f} € Risiko pro Trade."
    )

    apply_col1, apply_col2, apply_col3 = st.columns(3)

    with apply_col1:
        st.metric("Konto", f"{float(st.session_state.paper_cash):.2f} €")

    with apply_col2:
        st.metric("Risiko %", f"{profile_risk_pct:.2f}%")

    with apply_col3:
        st.metric("Risiko €", f"{profile_risk_eur:.2f} €")

    if st.button("Profil anwenden", key="apply_risk_profile_btn_v1", width="stretch"):
        apply_risk_profile_to_session(selected_profile)
        st.success(f"Risiko-Profil {selected_profile} wurde angewendet.")
        st.rerun()

def get_active_risk_profile_name() -> str:
    return str(st.session_state.get("paper_risk_profile_v1", "Unbekannt"))


def build_risk_profile_history_df():
    history = st.session_state.get("paper_history", [])
    if not history:
        return pd.DataFrame()

    df = pd.DataFrame(history).copy()

    if "Zeit" in df.columns:
        df["Zeit"] = pd.to_datetime(df["Zeit"], errors="coerce")

    if "Risiko-Profil" not in df.columns:
        df["Risiko-Profil"] = "Unbekannt"

    if "Realized PnL" not in df.columns:
        df["Realized PnL"] = 0.0

    df["Risiko-Profil"] = df["Risiko-Profil"].fillna("Unbekannt").astype(str)
    df["Realized PnL"] = pd.to_numeric(df["Realized PnL"], errors="coerce").fillna(0.0)

    return df


def build_risk_profile_review_df(history_df: pd.DataFrame):
    if history_df.empty or "Typ" not in history_df.columns:
        return pd.DataFrame()

    sells = history_df[history_df["Typ"].astype(str).str.lower() == "verkauf"].copy()
    if sells.empty:
        return pd.DataFrame()

    sells["Result"] = sells["Realized PnL"].apply(
        lambda x: "Gewinn" if x > 0 else "Verlust" if x < 0 else "Neutral"
    )

    return sells.reset_index(drop=True)


def calculate_risk_profile_statistics(review_df: pd.DataFrame):
    if review_df.empty:
        return pd.DataFrame()

    rows = []

    grouped = review_df.groupby("Risiko-Profil", dropna=False)

    for profile_name, group in grouped:
        wins = group[group["Realized PnL"] > 0]
        losses = group[group["Realized PnL"] < 0]

        win_rate = (group["Realized PnL"] > 0).mean() * 100 if len(group) > 0 else 0.0
        avg_win = wins["Realized PnL"].mean() if not wins.empty else 0.0
        avg_loss = losses["Realized PnL"].mean() if not losses.empty else 0.0
        total_pnl = group["Realized PnL"].sum()

        total_profit = wins["Realized PnL"].sum() if not wins.empty else 0.0
        total_loss = abs(losses["Realized PnL"].sum()) if not losses.empty else 0.0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0.0

        rows.append({
            "Risiko-Profil": profile_name,
            "Trades": int(len(group)),
            "Win Rate %": round(float(win_rate), 2),
            "Realized PnL": round(float(total_pnl), 2),
            "Ø Gewinn": round(float(avg_win), 2),
            "Ø Verlust": round(float(avg_loss), 2),
            "Profit Factor": round(float(profit_factor), 2)
        })

    result_df = pd.DataFrame(rows)
    if not result_df.empty:
        result_df = result_df.sort_values("Realized PnL", ascending=False).reset_index(drop=True)

    return result_df


def create_risk_profile_bar_figure(profile_stats_df: pd.DataFrame, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    fig = go.Figure()

    if not profile_stats_df.empty:
        fig.add_trace(
            go.Bar(
                x=profile_stats_df["Risiko-Profil"],
                y=profile_stats_df["Realized PnL"],
                name="Realized PnL"
            )
        )

    fig.update_layout(
        template=colors["template"],
        height=340,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="Risiko-Profil",
        yaxis_title="Realized PnL (€)",
        showlegend=False,
        title="Performance je Risiko-Profil"
    )

    fig.update_xaxes(gridcolor="rgba(120,180,255,0.08)")
    fig.update_yaxes(gridcolor="rgba(120,180,255,0.08)")

    return fig


def get_risk_profile_feedback(profile_stats_df: pd.DataFrame):
    if profile_stats_df.empty:
        return ["Noch nicht genug geschlossene Trades für eine Auswertung nach Risiko-Profil."]

    feedback = []

    best_row = profile_stats_df.iloc[0]
    best_profile = str(best_row["Risiko-Profil"])
    best_pnl = float(best_row["Realized PnL"])

    feedback.append(f"Aktuell ist **{best_profile}** dein bestes Risiko-Profil nach Realized PnL ({best_pnl:.2f} €).")

    if "Aggressiv" in profile_stats_df["Risiko-Profil"].values:
        agg_row = profile_stats_df[profile_stats_df["Risiko-Profil"] == "Aggressiv"].iloc[0]
        if float(agg_row["Profit Factor"]) < 1.0 and float(agg_row["Trades"]) >= 3:
            feedback.append("Das aggressive Profil wirkt aktuell weniger stabil. Vielleicht ist ein etwas defensiveres Risiko sinnvoll.")

    if "Konservativ" in profile_stats_df["Risiko-Profil"].values:
        cons_row = profile_stats_df[profile_stats_df["Risiko-Profil"] == "Konservativ"].iloc[0]
        if float(cons_row["Win Rate %"]) > 50 and float(cons_row["Trades"]) >= 3:
            feedback.append("Das konservative Profil zeigt eine stabile Trefferquote. Das kann für ruhigeres Lernen sehr hilfreich sein.")

    if len(feedback) == 0:
        feedback.append("Mit mehr Trades wird die Profil-Auswertung noch aussagekräftiger.")

    return feedback

def build_setup_statistics_df(notes_df: pd.DataFrame, review_df: pd.DataFrame):
    if notes_df.empty:
        return pd.DataFrame()

    working_df = notes_df.copy()

    # Falls Realized PnL aus dem Review noch nicht sauber drin ist
    if "Realized PnL" not in working_df.columns and not review_df.empty and "Realized PnL" in review_df.columns:
        merge_cols = [c for c in ["Zeit", "Symbol", "Order"] if c in working_df.columns and c in review_df.columns]
        if merge_cols:
            working_df = working_df.merge(
                review_df[merge_cols + ["Realized PnL"]],
                on=merge_cols,
                how="left"
            )

    if "Realized PnL" not in working_df.columns:
        working_df["Realized PnL"] = 0.0

    working_df["Realized PnL"] = pd.to_numeric(working_df["Realized PnL"], errors="coerce").fillna(0.0)

    if "Setup Quality" not in working_df.columns:
        working_df["Setup Quality"] = "Nicht bewertet"

    grouped_rows = []

    grouped = working_df.groupby("Setup Quality", dropna=False)

    for setup_name, group in grouped:
        wins = group[group["Realized PnL"] > 0]
        losses = group[group["Realized PnL"] < 0]

        win_rate = (group["Realized PnL"] > 0).mean() * 100 if len(group) > 0 else 0.0
        avg_win = wins["Realized PnL"].mean() if not wins.empty else 0.0
        avg_loss = losses["Realized PnL"].mean() if not losses.empty else 0.0
        total_pnl = group["Realized PnL"].sum()

        total_profit = wins["Realized PnL"].sum() if not wins.empty else 0.0
        total_loss = abs(losses["Realized PnL"].sum()) if not losses.empty else 0.0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0.0

        grouped_rows.append({
            "Setup": str(setup_name),
            "Trades": int(len(group)),
            "Win Rate %": round(float(win_rate), 2),
            "Realized PnL": round(float(total_pnl), 2),
            "Ø Gewinn": round(float(avg_win), 2),
            "Ø Verlust": round(float(avg_loss), 2),
            "Profit Factor": round(float(profit_factor), 2)
        })

    result_df = pd.DataFrame(grouped_rows)
    if not result_df.empty:
        result_df = result_df.sort_values("Realized PnL", ascending=False).reset_index(drop=True)

    return result_df


def create_setup_statistics_figure(setup_stats_df: pd.DataFrame, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    fig = go.Figure()

    if not setup_stats_df.empty:
        fig.add_trace(
            go.Bar(
                x=setup_stats_df["Setup"],
                y=setup_stats_df["Realized PnL"],
                name="Realized PnL"
            )
        )

    fig.update_layout(
        template=colors["template"],
        height=340,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="Setup",
        yaxis_title="Realized PnL (€)",
        showlegend=False,
        title="Performance je Setup"
    )

    fig.update_xaxes(gridcolor="rgba(120,180,255,0.08)")
    fig.update_yaxes(gridcolor="rgba(120,180,255,0.08)")

    return fig


def get_setup_statistics_feedback(setup_stats_df: pd.DataFrame):
    if setup_stats_df.empty:
        return ["Noch nicht genug bewertete Trades für eine Setup-Auswertung."]

    feedback = []

    best_row = setup_stats_df.iloc[0]
    best_setup = str(best_row["Setup"])
    best_pnl = float(best_row["Realized PnL"])

    feedback.append(f"Dein aktuell stärkstes Setup ist **{best_setup}** mit {best_pnl:.2f} € Realized PnL.")

    if "Nicht bewertet" in setup_stats_df["Setup"].values:
        unrated_row = setup_stats_df[setup_stats_df["Setup"] == "Nicht bewertet"].iloc[0]
        if float(unrated_row["Trades"]) >= 3:
            feedback.append("Viele Trades sind noch nicht bewertet. Deine Setup-Statistik wird stärker, wenn du mehr Reviews pflegst.")

    losing_setups = setup_stats_df[setup_stats_df["Realized PnL"] < 0]
    if not losing_setups.empty:
        weakest_setup = str(losing_setups.iloc[-1]["Setup"])
        feedback.append(f"Das schwächste Setup wirkt aktuell **{weakest_setup}**. Schau dir dort Entry, Exit und Fehler-Tags genauer an.")

    strong_pf = setup_stats_df[setup_stats_df["Profit Factor"] >= 1.2]
    if not strong_pf.empty:
        feedback.append("Mindestens ein Setup zeigt einen soliden Profit Factor. Das kann ein guter Kandidat für mehr Fokus im Training sein.")

    return feedback


def build_mistake_statistics_df(notes_df: pd.DataFrame):
    if notes_df.empty or "Mistake Tag" not in notes_df.columns:
        return pd.DataFrame()

    grouped = notes_df.groupby("Mistake Tag", dropna=False).size().reset_index(name="Anzahl")
    grouped["Mistake Tag"] = grouped["Mistake Tag"].astype(str)
    grouped = grouped.sort_values("Anzahl", ascending=False).reset_index(drop=True)

    return grouped


def create_mistake_statistics_figure(mistake_df: pd.DataFrame, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    fig = go.Figure()

    if not mistake_df.empty:
        fig.add_trace(
            go.Bar(
                x=mistake_df["Mistake Tag"],
                y=mistake_df["Anzahl"],
                name="Fehler"
            )
        )

    fig.update_layout(
        template=colors["template"],
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["font_color"]),
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="Fehler-Tag",
        yaxis_title="Anzahl",
        showlegend=False,
        title="Häufigkeit der Fehler-Tags"
    )

    fig.update_xaxes(gridcolor="rgba(120,180,255,0.08)")
    fig.update_yaxes(gridcolor="rgba(120,180,255,0.08)")

    return fig

def build_smart_insights(journal_notes_df: pd.DataFrame,
                         journal_review_df: pd.DataFrame,
                         risk_profile_stats_df: pd.DataFrame | None = None,
                         setup_stats_df: pd.DataFrame | None = None):
    insights = []

    if journal_review_df is None or journal_review_df.empty:
        return ["Noch nicht genug geschlossene Trades für Smart Insights."]

    closed_trades = len(journal_review_df)
    wins = int((journal_review_df["Realized PnL"] > 0).sum()) if "Realized PnL" in journal_review_df.columns else 0
    losses = int((journal_review_df["Realized PnL"] < 0).sum()) if "Realized PnL" in journal_review_df.columns else 0

    if closed_trades >= 5:
        if wins > losses:
            insights.append("Deine Gewinntrades überwiegen aktuell. Das ist ein gutes Zeichen für deine Grundrichtung.")
        elif losses > wins:
            insights.append("Deine Verlusttrades überwiegen aktuell. Prüfe vor allem Entry-Qualität, Risikohöhe und Geduld.")

    if journal_notes_df is not None and not journal_notes_df.empty:
        if "Mistake Tag" in journal_notes_df.columns:
            mistake_counts = journal_notes_df["Mistake Tag"].fillna("Unbekannt").value_counts()
            if not mistake_counts.empty:
                top_mistake = str(mistake_counts.index[0])
                if top_mistake != "Kein Fehler":
                    insights.append(f"Dein häufigster Fehler ist derzeit: **{top_mistake}**.")

        if "Emotion Tag" in journal_notes_df.columns:
            emotion_counts = journal_notes_df["Emotion Tag"].fillna("Unbekannt").value_counts()
            if not emotion_counts.empty:
                top_emotion = str(emotion_counts.index[0])
                if top_emotion == "FOMO":
                    insights.append("FOMO taucht häufig auf. Das spricht oft für späte Entries oder impulsive Entscheidungen.")
                elif top_emotion == "Angst":
                    insights.append("Angst ist in deinen Reviews oft sichtbar. Vielleicht ist deine Positionsgröße noch zu hoch.")
                elif top_emotion == "Gier":
                    insights.append("Gier taucht mehrfach auf. Prüfe, ob du Gewinne zu lange laufen lässt oder zu spät sicherst.")

        if "Plan Followed" in journal_notes_df.columns:
            known_plan_df = journal_notes_df[journal_notes_df["Plan Followed"].isin(["Ja", "Nein"])].copy()
            if not known_plan_df.empty:
                plan_rate = (known_plan_df["Plan Followed"] == "Ja").mean() * 100
                if plan_rate >= 70:
                    insights.append("Du hältst dich oft an deinen Plan. Das ist einer der wichtigsten Punkte für sauberes Trading.")
                elif plan_rate < 50:
                    insights.append("Du weichst noch häufig von deinem Plan ab. Genau dort steckt oft der größte Hebel für bessere Trades.")

    if risk_profile_stats_df is not None and not risk_profile_stats_df.empty:
        best_profile_row = risk_profile_stats_df.iloc[0]
        best_profile = str(best_profile_row["Risiko-Profil"])
        insights.append(f"Aktuell wirkt **{best_profile}** als dein stärkstes Risiko-Profil.")

        aggressive_rows = risk_profile_stats_df[risk_profile_stats_df["Risiko-Profil"] == "Aggressiv"]
        if not aggressive_rows.empty:
            agg_row = aggressive_rows.iloc[0]
            if float(agg_row["Profit Factor"]) < 1.0 and float(agg_row["Trades"]) >= 3:
                insights.append("Das aggressive Risiko-Profil wirkt bei dir noch instabil. Weniger Risiko könnte bessere Lernbedingungen schaffen.")

    if setup_stats_df is not None and not setup_stats_df.empty:
        best_setup_row = setup_stats_df.iloc[0]
        best_setup = str(best_setup_row["Setup"])
        insights.append(f"Dein aktuell stärkstes Setup ist **{best_setup}**.")

        weak_setups = setup_stats_df[setup_stats_df["Realized PnL"] < 0]
        if not weak_setups.empty:
            weakest_setup = str(weak_setups.iloc[-1]["Setup"])
            insights.append(f"Das schwächste Setup wirkt aktuell **{weakest_setup}**. Dort lohnt sich ein genauerer Blick auf Timing und Fehler.")

    if len(insights) == 0:
        insights.append("Es sind erste Daten vorhanden, aber noch nicht genug für aussagekräftige Coaching-Hinweise.")

    return insights


def build_smart_coaching_actions(journal_notes_df: pd.DataFrame,
                                 risk_profile_stats_df: pd.DataFrame | None = None,
                                 setup_stats_df: pd.DataFrame | None = None):
    actions = []

    if journal_notes_df is not None and not journal_notes_df.empty and "Mistake Tag" in journal_notes_df.columns:
        mistake_counts = journal_notes_df["Mistake Tag"].fillna("Unbekannt").value_counts()

        if "Zu früher Einstieg" in mistake_counts.index:
            actions.append("Warte bei neuen Trades häufiger auf Bestätigung statt sofort auf den ersten Impuls zu reagieren.")

        if "SL verschoben" in mistake_counts.index:
            actions.append("Lass den Stop-Loss nach dem Entry möglichst unverändert, außer dein Plan sieht klar etwas anderes vor.")

        if "Kein klarer Plan" in mistake_counts.index:
            actions.append("Definiere vor jedem Entry kurz: Einstieg, Stop-Loss, Ziel und maximal akzeptiertes Risiko.")

    if risk_profile_stats_df is not None and not risk_profile_stats_df.empty:
        conservative_rows = risk_profile_stats_df[risk_profile_stats_df["Risiko-Profil"] == "Konservativ"]
        aggressive_rows = risk_profile_stats_df[risk_profile_stats_df["Risiko-Profil"] == "Aggressiv"]

        if not conservative_rows.empty and not aggressive_rows.empty:
            cons_pnl = float(conservative_rows.iloc[0]["Realized PnL"])
            agg_pnl = float(aggressive_rows.iloc[0]["Realized PnL"])
            if cons_pnl > agg_pnl:
                actions.append("Nutze vorerst eher ein konservatives oder moderates Risiko-Profil, bis dein aggressives Profil stabilere Ergebnisse zeigt.")

    if setup_stats_df is not None and not setup_stats_df.empty:
        strong_setups = setup_stats_df[setup_stats_df["Profit Factor"] >= 1.2]
        if not strong_setups.empty:
            best_focus_setup = str(strong_setups.iloc[0]["Setup"])
            actions.append(f"Konzentriere dich in den nächsten Trades stärker auf das Setup **{best_focus_setup}**.")

    if len(actions) == 0:
        actions.append("Sammle noch etwas mehr bewertete Trades, damit konkrete Coaching-Aktionen besser abgeleitet werden können.")

    return actions


def render_smart_insights_cards(insights: list, title: str = "Smart Insight"):
    for line in insights:
        st.markdown(
            f"""
            <div class="em-card">
                <div class="em-card-title">{title}</div>
                <div class="em-card-sub">{line}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

def layout_wrap_start(width: str = "medium"):
    width = str(width).strip().lower()
    class_name = "em-medium-wrap"

    if width == "narrow":
        class_name = "em-narrow-wrap"
    elif width == "wide":
        class_name = "em-wide-wrap"
    elif width == "medium":
        class_name = "em-medium-wrap"

    st.markdown(f'<div class="em-center-wrap {class_name}">', unsafe_allow_html=True)


def layout_wrap_end():
    st.markdown('</div>', unsafe_allow_html=True)


def soft_divider():
    st.markdown('<div class="em-soft-divider"></div>', unsafe_allow_html=True)


def section_block_start(width: str = "medium"):
    layout_wrap_start(width=width)
    st.markdown('<div class="em-section-block">', unsafe_allow_html=True)


def section_block_end():
    st.markdown('</div>', unsafe_allow_html=True)
    layout_wrap_end()


def form_card_start():
    st.markdown('<div class="em-form-card">', unsafe_allow_html=True)


def form_card_end():
    st.markdown('</div>', unsafe_allow_html=True)


def subgrid_note(text: str):
    st.markdown(f'<div class="em-subgrid-note">{text}</div>', unsafe_allow_html=True)

def create_mini_price_chart_figure(mini_data: pd.DataFrame, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    fig = go.Figure()

    if mini_data is not None and not mini_data.empty and "Close" in mini_data.columns:
        fig.add_trace(
            go.Scatter(
                x=mini_data.index,
                y=mini_data["Close"],
                mode="lines",
                name="Preis"
            )
        )

    fig.update_layout(
        template=colors["template"],
        height=110,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["font_color"]),
        showlegend=False,
        xaxis=dict(showgrid=False, visible=False),
        yaxis=dict(showgrid=False, visible=False)
    )

    return fig

def create_mini_price_chart_figure(mini_data: pd.DataFrame, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    fig = go.Figure()

    if mini_data is not None and not mini_data.empty and "Close" in mini_data.columns:
        fig.add_trace(
            go.Scatter(
                x=mini_data.index,
                y=mini_data["Close"],
                mode="lines",
                name="Preis"
            )
        )

    fig.update_layout(
        template=colors["template"],
        height=120,
        margin=dict(l=4, r=4, t=4, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["font_color"]),
        showlegend=False,
        xaxis=dict(showgrid=False, visible=False),
        yaxis=dict(showgrid=False, visible=False)
    )

    return fig

def create_mini_price_chart_figure(mini_data: pd.DataFrame, chart_theme: str):
    colors = get_chart_colors_for_theme(chart_theme)

    fig = go.Figure()

    if mini_data is not None and not mini_data.empty and "Close" in mini_data.columns:
        fig.add_trace(
            go.Scatter(
                x=mini_data.index,
                y=mini_data["Close"],
                mode="lines",
                name="Preis"
            )
        )

    fig.update_layout(
        template=colors["template"],
        height=90,
        margin=dict(l=2, r=2, t=2, b=2),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(visible=False, showgrid=False),
        yaxis=dict(visible=False, showgrid=False)
    )

    return fig


saved_settings = load_user_settings()

if "show_onboarding" not in st.session_state:
    st.session_state.show_onboarding = saved_settings.get("show_onboarding", True)

if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

if "optimization_df" not in st.session_state:
    st.session_state.optimization_df = pd.DataFrame()

if "optimization_finished" not in st.session_state:
    st.session_state.optimization_finished = False

if "ticker" not in st.session_state:
    st.session_state.ticker = saved_settings.get("ticker", "TSLA")

if "symbol_mode" not in st.session_state:
    st.session_state.symbol_mode = saved_settings.get("symbol_mode", "Watchlist")

if "compare_input" not in st.session_state:
    st.session_state.compare_input = saved_settings.get("compare_input", "TSLA, AAPL, NVDA")

if "period" not in st.session_state:
    st.session_state.period = saved_settings.get("period", "3mo")

if "interval" not in st.session_state:
    st.session_state.interval = saved_settings.get("interval", "1d")

if "fee_percent" not in st.session_state:
    st.session_state.fee_percent = saved_settings.get("fee_percent", 0.1)

if "stop_loss_percent" not in st.session_state:
    st.session_state.stop_loss_percent = saved_settings.get("stop_loss_percent", 5.0)

if "take_profit_percent" not in st.session_state:
    st.session_state.take_profit_percent = saved_settings.get("take_profit_percent", 10.0)

if "use_rsi_filter" not in st.session_state:
    st.session_state.use_rsi_filter = saved_settings.get("use_rsi_filter", True)

if "rsi_min" not in st.session_state:
    st.session_state.rsi_min = saved_settings.get("rsi_min", 40.0)

if "rsi_max" not in st.session_state:
    st.session_state.rsi_max = saved_settings.get("rsi_max", 70.0)

if "use_ema200_filter" not in st.session_state:
    st.session_state.use_ema200_filter = saved_settings.get("use_ema200_filter", False)

if "show_trade_markers" not in st.session_state:
    st.session_state.show_trade_markers = saved_settings.get("show_trade_markers", True)

if "show_ema" not in st.session_state:
    st.session_state.show_ema = saved_settings.get("show_ema", True)

if "show_fibonacci" not in st.session_state:
    st.session_state.show_fibonacci = saved_settings.get("show_fibonacci", True)

if "show_support_resistance" not in st.session_state:
    st.session_state.show_support_resistance = saved_settings.get("show_support_resistance", True)

if "show_volume" not in st.session_state:
    st.session_state.show_volume = saved_settings.get("show_volume", True)

if "show_sl_tp_orders" not in st.session_state:
    st.session_state.show_sl_tp_orders = saved_settings.get("show_sl_tp_orders", True)

if "chart_theme" not in st.session_state:
    st.session_state.chart_theme = saved_settings.get("chart_theme", "Dark")

if "optimization_sl_input" not in st.session_state:
    st.session_state.optimization_sl_input = saved_settings.get("optimization_sl_input", "3,5,7")

if "optimization_tp_input" not in st.session_state:
    st.session_state.optimization_tp_input = saved_settings.get("optimization_tp_input", "6,10,15")

if "optimization_rsi_input" not in st.session_state:
    st.session_state.optimization_rsi_input = saved_settings.get("optimization_rsi_input", "35-75,40-70,45-65")

if "score_weight_return" not in st.session_state:
    st.session_state.score_weight_return = saved_settings.get("score_weight_return", 1.0)

if "score_weight_pf" not in st.session_state:
    st.session_state.score_weight_pf = saved_settings.get("score_weight_pf", 10.0)

if "score_weight_winrate" not in st.session_state:
    st.session_state.score_weight_winrate = saved_settings.get("score_weight_winrate", 0.2)

if "score_weight_drawdown" not in st.session_state:
    st.session_state.score_weight_drawdown = saved_settings.get("score_weight_drawdown", 1.0)

if "paper_cash" not in st.session_state:
    st.session_state.paper_cash = 10000.0

if "paper_equity_history" not in st.session_state:
    st.session_state.paper_equity_history = [{
        "Zeit": datetime.now(),
        "Cash": 10000.0,
        "Positionswert": 0.0,
        "Gesamtwert": 10000.0
    }]

if "paper_positions" not in st.session_state:
    st.session_state.paper_positions = {}

if "paper_history" not in st.session_state:
    st.session_state.paper_history = []

if "paper_open_orders" not in st.session_state:
    st.session_state.paper_open_orders = []

if "paper_start_cash" not in st.session_state:
    st.session_state.paper_start_cash = 10000.0

if "paper_trade_mode" not in st.session_state:
    st.session_state.paper_trade_mode = "Stückzahl"

if "paper_trade_amount" not in st.session_state:
    st.session_state.paper_trade_amount = 1000.0

if "paper_trade_quantity" not in st.session_state:
    st.session_state.paper_trade_quantity = 1

if "auto_sl_tp" not in st.session_state:
    st.session_state.auto_sl_tp = True

if "auto_sl_percent" not in st.session_state:
    st.session_state.auto_sl_percent = 5.0

if "auto_tp_percent" not in st.session_state:
    st.session_state.auto_tp_percent = 10.0

if "use_trailing_stop" not in st.session_state:
    st.session_state.use_trailing_stop = False

if "trailing_stop_percent" not in st.session_state:
    st.session_state.trailing_stop_percent = 5.0

if "show_paper_markers" not in st.session_state:
    st.session_state.show_paper_markers = saved_settings.get("show_paper_markers", True)

if "paper_benchmark" not in st.session_state:
    st.session_state.paper_benchmark = saved_settings.get("paper_benchmark", "SPY")

if "paper_benchmark_mode" not in st.session_state:
    st.session_state.paper_benchmark_mode = saved_settings.get("paper_benchmark_mode", "SPY")

if "paper_benchmark_custom" not in st.session_state:
    st.session_state.paper_benchmark_custom = saved_settings.get("paper_benchmark_custom", "SPY")

if "simple_trade_mode" not in st.session_state:
    st.session_state.simple_trade_mode = "Stückzahl"

if "simple_trade_amount" not in st.session_state:
    st.session_state.simple_trade_amount = 1000.0

if "simple_trade_qty" not in st.session_state:
    st.session_state.simple_trade_qty = 1

if "advanced_order_mode" not in st.session_state:
    st.session_state.advanced_order_mode = "Stückzahl"

if "advanced_order_qty" not in st.session_state:
    st.session_state.advanced_order_qty = 1

if "advanced_order_amount" not in st.session_state:
    st.session_state.advanced_order_amount = 1000.0

if "advanced_order_type" not in st.session_state:
    st.session_state.advanced_order_type = "Limit Buy"

if "trade_journal_notes" not in st.session_state:
    st.session_state.trade_journal_notes = {}

if "signal_center_category_filter" not in st.session_state:
    st.session_state.signal_center_category_filter = "Alle"

if "signal_center_priority_filter" not in st.session_state:
    st.session_state.signal_center_priority_filter = "Alle"

if "confirm_reset_watchlist" not in st.session_state:
    st.session_state.confirm_reset_watchlist = False

if "confirm_reset_journal" not in st.session_state:
    st.session_state.confirm_reset_journal = False

if "confirm_reset_paper" not in st.session_state:
    st.session_state.confirm_reset_paper = False

if "confirm_reset_settings" not in st.session_state:
    st.session_state.confirm_reset_settings = False

if "confirm_reset_all" not in st.session_state:
    st.session_state.confirm_reset_all = False

if "show_release_checklist" not in st.session_state:
    st.session_state.show_release_checklist = True

if "paper_trade_risk_eur_v1" not in st.session_state:
    st.session_state.paper_trade_risk_eur_v1 = 100.0

if "paper_trade_mode_v2" not in st.session_state:
    st.session_state.paper_trade_mode_v2 = "Stückzahl"

if "paper_risk_profile_v1" not in st.session_state:
    st.session_state.paper_risk_profile_v1 = "Moderat"

if "paper_trade_risk_percent_v1" not in st.session_state:
    st.session_state.paper_trade_risk_percent_v1 = 1.0

if "paper_trade_risk_eur_v1" in st.session_state:
    apply_risk_profile_to_session(st.session_state.paper_risk_profile_v1)

ticker = st.session_state.get("ticker", "TSLA")

ticker = st.session_state.ticker

process_limit_orders()

st.caption("Technische Marktanalyse mit EMA, RSI, MACD, Fibonacci, Support/Resistance und Backtesting.")

if st.session_state.get("show_onboarding", True):
    st.markdown("""
    <div class="em-section">
        <div class="em-kicker">Quick Start</div>
        <div><strong>Willkommen bei Emanacci</strong></div>
        <div style="opacity:0.85; margin-top:0.35rem;">
            Diese App hilft dir beim Analysieren, Backtesten und virtuellen Handeln von Aktien und Krypto.
        </div>
    </div>
    """, unsafe_allow_html=True)

    info_col1, info_col2 = st.columns([5, 1])

    with info_col1:
        st.info(
            "1. Wähle links ein Symbol aus der Watchlist oder suche eines.\n\n"
            "2. Prüfe Chart, Indikatoren und Signale im Analyse-Tab.\n\n"
            "3. Nutze Paper Trading für virtuelles Kaufen/Verkaufen.\n\n"
            "4. Vergleiche deine Performance mit Buy & Hold und teste Strategien im Backtesting."
        )

    with info_col2:
        if st.button("✖", key="close_onboarding"):
            st.session_state.show_onboarding = False
            st.rerun()

    st.markdown("""
    <div class="em-section">
        <div class="em-kicker">Dashboard</div>
        <div><strong>Schnellüberblick über Symbol, Depot und offene Orders</strong></div>
    </div>
    """, unsafe_allow_html=True)

    dashboard_price = None
    dashboard_open_pnl = 0.0
    dashboard_open_pnl_pct = 0.0
    dashboard_position_qty = 0
    dashboard_orders_count = len(st.session_state.paper_open_orders)

    try:
        dashboard_data = load_data(ticker, period="5d", interval="1d")
        if not dashboard_data.empty and "Close" in dashboard_data.columns:
            dashboard_price = float(dashboard_data["Close"].iloc[-1])
    except Exception:
        dashboard_price = None

    if ticker in st.session_state.paper_positions and dashboard_price is not None:
        pos = st.session_state.paper_positions[ticker]
        dashboard_position_qty = pos["quantity"]
        dashboard_total_cost = pos.get("total_cost", pos["quantity"] * pos["avg_price"])
        dashboard_market_value = pos["quantity"] * dashboard_price
        dashboard_open_pnl = dashboard_market_value - dashboard_total_cost
        dashboard_open_pnl_pct = (
            dashboard_open_pnl / dashboard_total_cost * 100
            if dashboard_total_cost > 0 else 0
        )

    dashboard_cash = st.session_state.paper_cash

    dashboard_positions_value = 0.0
    for symbol, pos in st.session_state.paper_positions.items():
        try:
            symbol_data = load_data(symbol, period="5d", interval="1d")
            if not symbol_data.empty and "Close" in symbol_data.columns:
                symbol_price = float(symbol_data["Close"].iloc[-1])
            else:
                symbol_price = pos["avg_price"]
        except Exception:
            symbol_price = pos["avg_price"]

        dashboard_positions_value += pos["quantity"] * symbol_price

    dashboard_total_value = dashboard_cash + dashboard_positions_value

    d1, d2, d3, d4, d5, d6 = st.columns(6)

    d1.metric("Aktives Symbol", ticker)
    d2.metric("Kurs", f"{dashboard_price:.2f} €" if dashboard_price is not None else "—")
    d3.metric("Position", f"{dashboard_position_qty} Stück")
    d4.metric("Offener PnL", f"{dashboard_open_pnl:.2f} €", f"{dashboard_open_pnl_pct:.2f}%")
    d5.metric("Cash", f"{dashboard_cash:,.2f} €")
    d6.metric("Offene Orders", f"{dashboard_orders_count}")

    st.caption(f"Depotwert gesamt: {dashboard_total_value:,.2f} €")

    if ticker in st.session_state.paper_positions:
        if dashboard_open_pnl > 0:
            st.success(f"{ticker}: offene Position im Gewinn ({dashboard_open_pnl:.2f} €)")
        elif dashboard_open_pnl < 0:
            st.warning(f"{ticker}: offene Position im Verlust ({dashboard_open_pnl:.2f} €)")
        else:
            st.info(f"{ticker}: offene Position aktuell bei Break-even")
    else:
        st.info(f"Für {ticker} ist aktuell keine offene Paper-Position vorhanden.")

    st.markdown("---")

with st.sidebar:
    st.markdown("## Steuerung")

    render_sidebar_panel(
        "Markt & Symbol",
        "Wähle hier dein Symbol und die Grunddaten für die App."
    )

    symbol_mode_options = ["Watchlist", "Freies Symbol"]
    selected_symbol_mode = st.radio(
        "Symbolmodus",
        symbol_mode_options,
        index=symbol_mode_options.index(st.session_state.symbol_mode)
        if st.session_state.symbol_mode in symbol_mode_options else 0,
        key="sidebar_symbol_mode_clean"
    )
    st.session_state.symbol_mode = selected_symbol_mode

    if st.session_state.symbol_mode == "Watchlist":
        if not st.session_state.watchlist:
            st.session_state.watchlist = ["TSLA", "AAPL", "NVDA"]

        selected_watchlist_symbol = st.selectbox(
            "Watchlist Symbol",
            st.session_state.watchlist,
            index=st.session_state.watchlist.index(st.session_state.ticker)
            if st.session_state.ticker in st.session_state.watchlist else 0,
            key="sidebar_watchlist_symbol_clean"
        )
        st.session_state.ticker = selected_watchlist_symbol
    else:
        free_symbol_value = st.text_input(
            "Freies Symbol",
            value=st.session_state.ticker,
            key="sidebar_free_symbol_clean"
        ).upper().strip()

        if free_symbol_value:
            st.session_state.ticker = free_symbol_value

    render_sidebar_panel(
        "Preset",
        "Nutze ein Preset als schnellen Startpunkt."
    )

    preset_names = list(PRESETS.keys())
    current_preset_name = st.session_state.get("selected_preset_name", preset_names[0])

    selected_preset_name = st.selectbox(
        "Preset wählen",
        preset_names,
        index=preset_names.index(current_preset_name) if current_preset_name in preset_names else 0,
        key="sidebar_preset_select_clean"
    )

    st.caption(get_preset_description(selected_preset_name))

    apply_selected_preset = st.button(
        "Preset anwenden",
        key="sidebar_apply_preset_clean",
        width="stretch"
    )

    if apply_selected_preset:
        apply_preset_to_session(selected_preset_name)
        save_user_settings({
            **load_user_settings(),
            "ticker": st.session_state.ticker,
            "symbol_mode": st.session_state.symbol_mode,
            "compare_input": st.session_state.get("compare_input", "TSLA, AAPL, NVDA"),
            "period": st.session_state.period,
            "interval": st.session_state.interval,
            "chart_theme": st.session_state.chart_theme,
            "show_onboarding": st.session_state.show_onboarding,
        })
        st.success(f"Preset {selected_preset_name} wurde angewendet.")
        st.rerun()

    render_sidebar_panel(
        "Marktdaten",
        "Zeitraum und Anzeige für Analyse und Vergleich."
    )

    sidebar_period_options = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y"]
    sidebar_interval_options = ["1m", "5m", "15m", "1h", "1d"]

    st.session_state.period = st.selectbox(
        "Zeitraum",
        sidebar_period_options,
        index=sidebar_period_options.index(st.session_state.period)
        if st.session_state.period in sidebar_period_options else 3,
        key="sidebar_period_clean"
    )

    st.session_state.interval = st.selectbox(
        "Intervall",
        sidebar_interval_options,
        index=sidebar_interval_options.index(st.session_state.interval)
        if st.session_state.interval in sidebar_interval_options else 2,
        key="sidebar_interval_clean"
    )

    st.session_state.chart_theme = st.selectbox(
        "Theme",
        ["Dark", "Light"],
        index=0 if st.session_state.chart_theme == "Dark" else 1,
        key="sidebar_chart_theme_clean"
    )

    render_sidebar_panel(
        "Strategie & Risiko",
        "Einfache Grundwerte für Tests und Analyse."
    )

    risk_col1, risk_col2 = st.columns(2)

    with risk_col1:
        st.session_state.fee_percent = st.number_input(
            "Gebühr %",
            min_value=0.0,
            value=float(st.session_state.fee_percent),
            step=0.01,
            key="sidebar_fee_percent_clean"
        )

        st.session_state.stop_loss_percent = st.number_input(
            "SL %",
            min_value=0.0,
            value=float(st.session_state.stop_loss_percent),
            step=0.5,
            key="sidebar_sl_percent_clean"
        )

    with risk_col2:
        st.session_state.take_profit_percent = st.number_input(
            "TP %",
            min_value=0.0,
            value=float(st.session_state.take_profit_percent),
            step=0.5,
            key="sidebar_tp_percent_clean"
        )

        st.session_state.trailing_stop_percent = st.number_input(
            "Trailing %",
            min_value=0.0,
            value=float(st.session_state.trailing_stop_percent),
            step=0.5,
            key="sidebar_trailing_percent_clean"
        )

    st.session_state.use_rsi_filter = st.checkbox(
        "RSI Filter nutzen",
        value=bool(st.session_state.use_rsi_filter),
        key="sidebar_use_rsi_filter_clean"
    )

    if st.session_state.use_rsi_filter:
        rsi_col1, rsi_col2 = st.columns(2)

        with rsi_col1:
            st.session_state.rsi_min = st.number_input(
                "RSI Min",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state.rsi_min),
                step=1.0,
                key="sidebar_rsi_min_clean"
            )

        with rsi_col2:
            st.session_state.rsi_max = st.number_input(
                "RSI Max",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state.rsi_max),
                step=1.0,
                key="sidebar_rsi_max_clean"
            )

    st.session_state.use_ema200_filter = st.checkbox(
        "EMA200 Filter nutzen",
        value=bool(st.session_state.use_ema200_filter),
        key="sidebar_use_ema200_filter_clean"
    )

    render_sidebar_panel(
        "App",
        "Kleine globale Einstellungen."
    )

    if st.session_state.show_onboarding:
        render_onboarding_guide()

    save_settings_now = st.button(
        "Einstellungen speichern",
        key="sidebar_save_settings_clean",
        width="stretch"
    )

    if save_settings_now:
        save_user_settings({
            "ticker": st.session_state.ticker,
            "symbol_mode": st.session_state.symbol_mode,
            "compare_input": st.session_state.get("compare_input_clean", st.session_state.get("compare_input", "TSLA, AAPL, NVDA")),
            "period": st.session_state.period,
            "interval": st.session_state.interval,
            "chart_theme": st.session_state.chart_theme,
            "show_onboarding": st.session_state.show_onboarding,
        })
        st.success("Einstellungen wurden gespeichert.")

    section_header(
        "Schnell-Backup",
        "Lade ein vollständiges Backup deiner aktuellen App-Daten herunter."
    )

    st.download_button(
        "Backup JSON",
        data=dict_to_json_bytes(build_full_backup_dict()),
        file_name="emanacci_backup.json",
        mime="application/json",
        key="download_quick_backup_json",
        width="stretch"
    )

chart_theme = st.session_state.chart_theme

if chart_theme == "Dark":
    chart_bg = "#08101f"
    paper_bg = "#050914"
    font_color = "#dfe7ff"
    grid_color = "rgba(120, 180, 255, 0.08)"
else:
    chart_bg = "rgba(245, 248, 255, 0.96)"
    paper_bg = "rgba(255, 255, 255, 0.98)"
    font_color = "#111111"
    grid_color = "rgba(0, 0, 0, 0.08)"

data = load_data(
    ticker,
    period=st.session_state.period,
    interval=st.session_state.interval
)

tab_analyse, tab_advanced, tab_vergleich, tab_paper, tab_watchlist = st.tabs(
    ["Analyse", "Advanced", "Vergleich", "Paper Trading", "Watchlist"]
)

with tab_watchlist:

    section_block_start("wide")
    render_hero(
        "Watchlist & Scanner",
        "Behalte interessante Märkte im Blick, filtere starke oder schwache Werte und springe direkt in Analyse oder Paper Trading."
    )
    section_block_end()

    section_block_start("wide")

    section_header(
        "Watchlist Pro",
        "Hier siehst du Preis, Trend, RSI und wichtige Kategorien deiner beobachteten Symbole."
    )

    watchlist = st.session_state.get("watchlist", [])

    if not watchlist:
        st.info("Keine Werte in der Watchlist.")
    else:

        results = []

        for symbol in watchlist:
            try:
                data = load_data(symbol, period=period, interval=interval)
                data = calculate_indicators(data)

                metrics = build_watchlist_metrics(data)
                category = classify_symbol(metrics)

                results.append({
                    "Symbol": symbol,
                    "Preis": metrics["price"],
                    "Change %": metrics["change_pct"],
                    "RSI": metrics["rsi"],
                    "Trend": metrics["trend"],
                    "Kategorie": category
                })

            except Exception:
                continue

        df = pd.DataFrame(results)

        st.write(df.columns.tolist())

        alerts_df = build_watchlist_alerts(
            symbols=watchlist,
            period=period,
            interval=interval
        )

        # ----------------------------------------------------
        # FILTER
        # ----------------------------------------------------

        st.selectbox(
            "Kategorie filtern",
            [...],
            help="Filtert deine Watchlist nach bestimmten Marktbedingungen"
        )

        filter_col1, filter_col2 = st.columns(2)

        with filter_col1:
            category_filter = st.selectbox(
                "Kategorie filtern",
                ["Alle", "Trend Long", "Trend Schwach", "Überkauft", "Überverkauft", "Neutral"],
                key="watchlist_category_filter"
            )

        with filter_col2:
            sort_by = st.selectbox(
                "Sortieren nach",
                ["Change %", "RSI"],
                key="watchlist_sort_by"
            )

        filtered_df = df.copy()

        if category_filter != "Alle":
            filtered_df = filtered_df[filtered_df["Kategorie"] == category_filter]

        filtered_df = filtered_df.sort_values(sort_by, ascending=False)

        # ----------------------------------------------------
        # WATCHLIST CARDS
        # ----------------------------------------------------

        section_header(
            "Übersicht",
            "Schneller Überblick über deine aktuellen Watchlist-Kandidaten."
        )

        for i in range(0, len(filtered_df), 2):
            card_col1, card_col2 = st.columns(2)

            for col, idx in zip([card_col1, card_col2], [i, i + 1]):
                if idx >= len(filtered_df):
                    continue

                row = filtered_df.iloc[idx]
                color = "green" if row["Change %"] > 0 else "red"

                with col:
                    st.markdown('<div class="em-watch-card-shell">', unsafe_allow_html=True)

                    info_col, chart_col = st.columns([1.6, 1.0])

                    symbol_value = row.get("Symbol", "-")
                    price_value = float(row.get("Preis", row.get("price", 0.0)))
                    perf_value = float(row.get("Performance", row.get("Change %", row.get("change_pct", 0.0))))
                    day_change_value = float(row.get("Tagesänderung", row.get("Day Change %", row.get("day_change_pct", 0.0))))
                    trend_value = row.get("Trend", row.get("trend", "-"))
                    rsi_value = float(row.get("RSI", row.get("rsi", 0.0)))

                    with info_col:
                        st.markdown(f"""
                        <div class="em-card">
                            <div class="em-card-title">{symbol_value}</div>
                            <div class="em-card-sub">Preis: <span class="em-card-number">{price_value:.2f} €</span></div>
                            <div class="em-card-sub">Performance: <span class="em-card-number">{perf_value:.2f}%</span></div>
                            <div class="em-card-sub">Tagesänderung: <span class="em-card-number">{day_change_value:.2f}%</span></div>
                            <div class="em-card-sub">Trend: {trend_value}</div>
                            <div class="em-card-sub">RSI: <span class="em-card-number">{rsi_value:.2f}</span></div>
                        </div>
                        """, unsafe_allow_html=True)

                    with chart_col:
                        try:
                            mini_data = load_data(symbol_value, period="1mo", interval="1d")
                            mini_data = calculate_indicators(mini_data)

                            mini_fig = create_mini_price_chart_figure(
                                mini_data,
                                st.session_state.chart_theme
                            )

                            st.plotly_chart(
                                mini_fig,
                                width="stretch",
                                key=f"overview_mini_{symbol_value}"
                            )
                        except Exception:
                            st.caption("Kein Chart verfügbar")

                    st.markdown('</div>', unsafe_allow_html=True)

                button_col1, button_col2 = st.columns(2)

                with button_col1:
                    if st.button("Analyse", key=f"watch_analyse_{idx}", width="stretch"):
                        st.session_state.ticker = row["Symbol"]
                        st.success(f"{row['Symbol']} wurde für die Analyse gewählt.")
                        st.rerun()

                with button_col2:
                    if st.button("Trade", key=f"watch_trade_{idx}", width="stretch"):
                        st.session_state.ticker = row["Symbol"]
                        st.success(f"{row['Symbol']} wurde für Paper Trading gewählt.")
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)


        panel_note(
            "Hinweis",
            "Der Scanner zeigt mögliche interessante Situationen, ersetzt aber keine eigene Analyse. Nutze ihn als schnellen Einstiegspunkt."
        )

        # ----------------------------------------------------
        # MARKT SCANNER
        # ----------------------------------------------------

        st.markdown("---")
        section_header(
            "Markt Scanner",
            "Hier findest du starke, schwache und auffällige Werte aus deiner Watchlist in kompakter Form."
        )

        scanner_col1, scanner_col2 = st.columns(2)

        with scanner_col1:
            st.write("🔥 Stärkste Werte")
            top = df.sort_values("Change %", ascending=False).head(5)
            st.dataframe(top[["Symbol", "Change %"]], width="stretch")

            st.write("📈 Trend Long")
            trend_long = df[df["Kategorie"] == "Trend Long"]
            st.dataframe(trend_long[["Symbol", "RSI"]], width="stretch")

        with scanner_col2:
            st.write("❄️ Schwächste Werte")
            worst = df.sort_values("Change %", ascending=True).head(5)
            st.dataframe(worst[["Symbol", "Change %"]], width="stretch")

            st.write("⚠️ Überkauft / Überverkauft")
            extremes = df[df["Kategorie"].isin(["Überkauft", "Überverkauft"])]
            st.dataframe(extremes[["Symbol", "RSI"]], width="stretch")

        # ----------------------------------------------------
        # SIGNAL CENTER
        # ----------------------------------------------------

        st.markdown("---")
        section_header(
            "Signal Center",
            "Automatisch erkannte Marktsituationen in einfacher Sprache – inklusive Priorität und Quick Actions."
        )
        render_signal_center(alerts_df)

        ui_gap("sm")
        panel_note(
            "Scanner-Tipp",
            "Konzentriere dich nicht auf zu viele Symbole gleichzeitig. Wenige, gut beobachtete Märkte helfen oft mehr als eine zu große Watchlist."
        )

    section_block_end()

def calculate_quantity_from_amount(amount, price):
    if price <= 0:
        return 0
    return round(amount / price, 4)


def calculate_trade_risk(entry, stop, quantity):
    if not entry or not stop or quantity <= 0:
        return None, None

    risk_per_unit = entry - stop
    total_risk = risk_per_unit * quantity

    risk_pct = (risk_per_unit / entry) * 100 if entry > 0 else None

    return total_risk, risk_pct


with tab_paper:

    paper_tab_trade, paper_tab_positions, paper_tab_journal, paper_tab_learning, paper_tab_data = st.tabs(
        ["Trading", "Positionen & Orders", "Journal", "Learning", "Daten"]
    )

    # ========================================================
    # TAB 1 — TRADING
    # ========================================================
    with paper_tab_trade:

        render_context_hint(
            "Was passiert hier?",
            "Du kannst hier Trades simulieren, ohne echtes Geld zu riskieren."
        )

        render_hero(
            "Paper Trading",
            "Teste Ideen ohne echtes Risiko, beobachte Positionen, verwalte Orders und lerne aus deiner Historie."
        )

        section_header(
            "Vorbereitete Trade-Idee",
            "Wenn du im Analyse-Tab eine Idee markiert hast, erscheint sie hier als Lernhilfe."
        )
        render_paper_trade_idea_box()

        ui_gap("sm")

        # -------------------------------
        # ZENTRIERTER EINGABEBEREICH
        # -------------------------------
        outer_left, center, outer_right = st.columns([1, 2, 1])

        with center:

            section_block_start("narrow")

            section_header(
                "Trade eingeben",
                "Du kannst nach Stückzahl, Betrag oder Risiko handeln. Stop-Loss und Take-Profit lassen sich direkt mit vorbereiten."
            )

            subgrid_note("Dieser Bereich ist absichtlich kompakter gehalten, damit Trading-Aktionen schneller im Fokus bleiben.")

            form_card_start()

            current_price = float(data["Close"].iloc[-1])
            trade_time = data.index[-1] if len(data.index) > 0 else None

            process_all_open_orders({ticker: current_price}, trade_time)

            default_sl = st.session_state.get("trade_idea_prefill_sl")
            default_tp = st.session_state.get("trade_idea_prefill_tp")

            input_col1, input_col2 = st.columns(2)

            with input_col1:
                stop_loss = st.number_input(
                    "Stop-Loss",
                    value=float(default_sl) if default_sl else 0.0,
                    step=0.1,
                    key="paper_direct_stop_loss_v2",
                    help="Preis, bei dem dein Trade automatisch mit Verlust beendet werden soll."
                )

            with input_col2:
                take_profit = st.number_input(
                    "Take-Profit",
                    value=float(default_tp) if default_tp else 0.0,
                    step=0.1,
                    key="paper_direct_take_profit_v2",
                    help="Preis, bei dem dein Trade automatisch im Gewinn beendet werden soll."
                )

            render_risk_profile_panel()

            ui_gap("sm")

            mode = st.radio(
                "Modus",
                ["Stückzahl", "Betrag (€)", "Risiko (€)"],
                horizontal=True,
                key="paper_trade_mode_v2",
                help="Wähle, ob du direkt Stück, einen festen Betrag oder ein maximales Risiko pro Trade eingeben willst."
            )

            quantity = 0

            if mode == "Stückzahl":
                entered_qty = st.number_input(
                    "Stückzahl",
                    min_value=0.0,
                    step=0.01,
                    format="%.4f",
                    key="paper_trade_qty_v2",
                    help="Direkte Anzahl der Stücke, die du kaufen oder verkaufen möchtest. Bruchstücke sind erlaubt."
                )
                quantity = normalize_trade_quantity(entered_qty)

            elif mode == "Betrag (€)":
                entered_amount = st.number_input(
                    "Betrag (€)",
                    min_value=0.0,
                    step=100.0,
                    key="paper_trade_amount_v2",
                    help="Wie viel € du für diesen Trade einsetzen möchtest."
                )
                quantity = normalize_trade_quantity(
                    calculate_quantity_from_amount(entered_amount, current_price)
                )
                st.caption(f"≈ {quantity:.4f} Stück")

            else:
                entered_risk_eur = st.number_input(
                    "Max. Risiko (€)",
                    min_value=0.0,
                    step=10.0,
                    key="paper_trade_risk_eur_v1",
                    help="Maximaler Verlust in Euro, den du bei Erreichen des Stop-Loss akzeptieren willst."
                )

                if stop_loss > 0 and stop_loss < current_price:
                    quantity = calculate_quantity_from_risk_amount(
                        entry_price=current_price,
                        stop_loss_price=stop_loss,
                        risk_amount=entered_risk_eur
                    )
                    st.caption(f"≈ {quantity} Stück auf Basis des gewählten Risikos")
                else:
                    quantity = 0
                    st.warning("Für den Risiko-Modus brauchst du einen gültigen Stop-Loss unter dem Einstieg.")

            quick_col1, quick_col2, quick_col3 = st.columns(3)

            with quick_col1:
                if st.button("25% Cash", key="paper_quick_25", width="stretch"):
                    quick_qty = normalize_trade_quantity(
                        calculate_quantity_from_amount(st.session_state.paper_cash * 0.25, current_price)
                    )
                    st.session_state.paper_trade_qty_v2 = float(quick_qty)
                    st.session_state.paper_trade_mode_v2 = "Stückzahl"
                    st.rerun()

            with quick_col2:
                if st.button("50% Cash", key="paper_quick_50", width="stretch"):
                    quick_qty = normalize_trade_quantity(
                        calculate_quantity_from_amount(st.session_state.paper_cash * 0.50, current_price)
                    )
                    st.session_state.paper_trade_qty_v2 = float(quick_qty)
                    st.session_state.paper_trade_mode_v2 = "Stückzahl"
                    st.rerun()

            with quick_col3:
                if st.button("100% Cash", key="paper_quick_100", width="stretch"):
                    quick_qty = normalize_trade_quantity(
                        calculate_quantity_from_amount(st.session_state.paper_cash, current_price)
                    )
                    st.session_state.paper_trade_qty_v2 = float(quick_qty)
                    st.session_state.paper_trade_mode_v2 = "Stückzahl"
                    st.rerun()

            risk, risk_pct = calculate_trade_risk(current_price, stop_loss, quantity)

            info_col1, info_col2, info_col3 = st.columns(3)

            with info_col1:
                st.metric("Aktueller Preis", f"{current_price:.2f} €")

            with info_col2:
                st.metric("Geplante Stück", f"{quantity:.4f}")

            with info_col3:
                est_value = current_price * quantity
                st.metric("Positionswert", f"{est_value:.2f} €")

            if risk is not None and stop_loss > 0 and quantity > 0:
                st.info(f"Max. Risiko bis Stop-Loss: {risk:.2f} € ({risk_pct:.2f}%)")

            position_summary = get_position_sizing_summary(
                entry_price=current_price,
                stop_loss_price=stop_loss,
                quantity=quantity,
                account_size=st.session_state.paper_cash
            )

            size_col1, size_col2, size_col3 = st.columns(3)

            with size_col1:
                st.metric("Positionswert", f"{position_summary['position_value']:.2f} €")

            with size_col2:
                st.metric("Risiko in €", f"{position_summary['trade_risk_eur']:.2f} €")

            with size_col3:
                st.metric("Konto-Risiko", f"{position_summary['account_risk_pct']:.2f}%")

            if mode == "Risiko (€)" and stop_loss > 0 and quantity < 1:
                panel_note(
                    "Hinweis zur Positionsgröße",
                    "Mit dem gewählten Stop-Loss und Risiko ergibt sich aktuell keine handelbare Stückzahl. Entweder Risiko erhöhen oder Stop-Loss weiter wählen."
                )

            action_col1, action_col2 = st.columns(2)

            with action_col1:
                if st.button("Kaufen", key="paper_buy_real_v2", width="stretch"):
                    success, message = execute_paper_buy(
                        symbol=ticker,
                        quantity_value=quantity,
                        price=current_price,
                        trade_time=trade_time,
                        order_name="Market Buy"
                    )

                    if success:
                        add_exit_orders_after_buy(
                            symbol=ticker,
                            quantity_value=quantity,
                            stop_loss_value=stop_loss,
                            take_profit_value=take_profit
                        )
                        st.success(message)
                        st.rerun()
                    else:
                        st.warning(message)

            with action_col2:
                if st.button("Verkaufen", key="paper_sell_real_v2", width="stretch"):
                    success, message = execute_paper_sell(
                        symbol=ticker,
                        quantity_value=quantity,
                        price=current_price,
                        trade_time=trade_time,
                        order_name="Market Sell"
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.warning(message)

            form_card_end()
            section_block_end()

        ui_gap("sm")
        panel_note(
            "Lernhinweis",
            "Nutze Risiko-Profile und den Risiko-Modus, um Trades nicht nur nach Gefühl, sondern strukturiert zu planen."
        )

    # ========================================================
    # TAB 2 — POSITIONEN & ORDERS
    # ========================================================
    with paper_tab_positions:

        current_price = float(data["Close"].iloc[-1])
        trade_time = data.index[-1] if len(data.index) > 0 else None

        section_header(
            "Offene Positionen",
            "Hier siehst du aktuelle Positionen inklusive PnL und schnellen Teilverkaufs-Aktionen."
        )

        position = get_open_position_for_symbol(ticker)

        if position:
            held_qty = int(position["quantity"])
            avg_price = float(position["avg_price"])
            pnl_value, pnl_pct = get_position_pnl_for_symbol(ticker, current_price)

            border_class = "em-card-positive" if pnl_value > 0 else "em-card-negative" if pnl_value < 0 else ""

            st.markdown(
                f"""
                <div class="em-card {border_class}">
                    <div class="em-card-title">{ticker}</div>
                    <div class="em-card-sub">Stück: {held_qty:.4f}</div>
                    <div class="em-card-sub">Ø Preis: {avg_price:.2f} €</div>
                    <div class="em-card-sub">Aktueller Preis: {current_price:.2f} €</div>
                    <div class="em-card-sub"><strong>PnL: {pnl_value:.2f} € ({pnl_pct:.2f}%)</strong></div>
                </div>
                """,
                unsafe_allow_html=True
            )

            pos_col1, pos_col2, pos_col3 = st.columns(3)

            with pos_col1:
                sell_25_qty = round(max(held_qty * 0.25, min(held_qty, 0.0001)), 6)
                if st.button("25% verkaufen", key=f"paper_sell_25_{ticker}", width="stretch"):
                    success, message = execute_paper_sell(
                        symbol=ticker,
                        quantity_value=min(sell_25_qty, held_qty),
                        price=current_price,
                        trade_time=trade_time,
                        order_name="Partial Sell 25%"
                    )
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.warning(message)

            with pos_col2:
                sell_50_qty = round(max(held_qty * 0.50, min(held_qty, 0.0001)), 6)
                if st.button("50% verkaufen", key=f"paper_sell_50_{ticker}", width="stretch"):
                    success, message = execute_paper_sell(
                        symbol=ticker,
                        quantity_value=min(sell_50_qty, held_qty),
                        price=current_price,
                        trade_time=trade_time,
                        order_name="Partial Sell 50%"
                    )
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.warning(message)

            with pos_col3:
                if st.button("Alles verkaufen", key=f"paper_sell_all_{ticker}", width="stretch"):
                    success, message = execute_paper_sell(
                        symbol=ticker,
                        quantity_value=held_qty,
                        price=current_price,
                        trade_time=trade_time,
                        order_name="Close Position"
                    )
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.warning(message)
        else:
            st.info("Keine Position offen.")

        st.markdown("---")
        section_header(
            "Offene Orders",
            "Alle aktiven Limit-, Schutz- und Trailing-Orders auf einen Blick."
        )
        render_open_orders_ui()

    # ========================================================
    # TAB 3 — JOURNAL
    # ========================================================
    with paper_tab_journal:

        section_header(
            "Trade Historie",
            "Hier siehst du deine bisherigen Paper-Trades kompakt als Karten und vollständig in der Tabelle."
        )
        render_trade_history_simple()

        st.markdown("---")
        section_header(
            "Trade Journal & Review",
            "Bewerte geschlossene Trades, erkenne Muster und verbessere Schritt für Schritt dein Entscheidungsverhalten."
        )

        journal_history_df = build_trade_journal_dataframe()
        journal_review_df = build_closed_trades_review_df(journal_history_df)

        if journal_history_df.empty:
            st.info("Noch keine Trade-Daten vorhanden.")
        else:
            journal_metrics = calculate_trade_journal_metrics(journal_review_df, journal_history_df)
            render_trade_journal_metrics(journal_metrics)

            feedback_lines = get_journal_feedback(journal_metrics)
            render_trade_journal_feedback(feedback_lines)

            if not journal_review_df.empty:
                filter_col1, filter_col2 = st.columns(2)

                available_symbols = ["Alle"] + sorted(journal_review_df["Symbol"].dropna().astype(str).unique().tolist())
                available_results = ["Alle", "Gewinn", "Verlust", "Neutral"]

                with filter_col1:
                    selected_journal_symbol = st.selectbox(
                        "Symbol filtern",
                        available_symbols,
                        key="journal_symbol_filter"
                    )

                with filter_col2:
                    selected_journal_result = st.selectbox(
                        "Ergebnis filtern",
                        available_results,
                        key="journal_result_filter"
                    )

                filtered_review_df = journal_review_df.copy()

                if selected_journal_symbol != "Alle":
                    filtered_review_df = filtered_review_df[
                        filtered_review_df["Symbol"].astype(str) == selected_journal_symbol
                    ]

                if selected_journal_result != "Alle":
                    filtered_review_df = filtered_review_df[
                        filtered_review_df["Result"].astype(str) == selected_journal_result
                    ]

                if filtered_review_df.empty:
                    st.info("Für diese Filter gibt es aktuell keine geschlossenen Trades.")
                else:
                    st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
                    journal_fig = create_journal_pnl_figure(filtered_review_df, st.session_state.chart_theme)
                    st.plotly_chart(
                        journal_fig,
                        width="stretch",
                        key="journal_trade_pnl_chart"
                    )
                    st.markdown('</div>', unsafe_allow_html=True)

                    symbol_summary_df = build_symbol_review_summary(filtered_review_df)
                    if not symbol_summary_df.empty:
                        with st.expander("📊 Symbol-Auswertung", expanded=False):
                            st.dataframe(symbol_summary_df, width="stretch")

                    with st.expander("📋 Geschlossene Trades im Review", expanded=False):
                        display_df = filtered_review_df.copy()
                        if "Zeit" in display_df.columns:
                            display_df["Zeit"] = pd.to_datetime(display_df["Zeit"], errors="coerce").dt.strftime("%d.%m.%Y %H:%M")
                        st.dataframe(display_df, width="stretch")
            else:
                st.info("Es gibt bisher noch keine geschlossenen Trades für die Auswertung.")

        st.markdown("---")
        section_header(
            "Trade Journal Pro",
            "Ergänze Bewertungen, Fehler-Tags, Emotionen und Notizen pro geschlossenem Trade."
        )

        journal_notes_df = build_trade_notes_dataframe(journal_review_df)

        if journal_review_df.empty:
            st.info("Sobald du geschlossene Trades hast, kannst du sie hier detailliert bewerten.")
        else:
            learning_metrics = calculate_journal_learning_metrics(journal_notes_df)
            render_learning_metrics(learning_metrics)

            feedback_lines = build_learning_feedback(journal_notes_df, learning_metrics)
            render_learning_feedback(feedback_lines)

            st.write("#### Trade bewerten")

            review_options = [
                f"{idx+1}. {str(row.get('Symbol', '-'))} | {str(row.get('Typ', '-'))} | "
                f"{pd.to_datetime(row.get('Zeit'), errors='coerce').strftime('%d.%m.%Y %H:%M') if pd.notna(row.get('Zeit')) else '-'} | "
                f"PnL: {float(row.get('Realized PnL', 0)):.2f} €"
                for idx, row in journal_review_df.reset_index(drop=True).iterrows()
            ]

            selected_trade_idx = st.selectbox(
                "Geschlossenen Trade auswählen",
                range(len(review_options)),
                format_func=lambda i: review_options[i],
                key="journal_trade_picker_v2"
            )

            selected_trade_row = journal_review_df.reset_index(drop=True).iloc[selected_trade_idx]
            selected_note_key = build_trade_note_key(selected_trade_row, selected_trade_idx)
            selected_payload = get_trade_note_payload(selected_note_key)

            note_col1, note_col2 = st.columns(2)

            with note_col1:
                setup_quality = st.selectbox(
                    "Setup-Qualität",
                    ["Nicht bewertet", "Schlecht", "Okay", "Gut", "Sehr gut"],
                    index=["Nicht bewertet", "Schlecht", "Okay", "Gut", "Sehr gut"].index(selected_payload.get("setup_quality", "Nicht bewertet")),
                    key=f"setup_quality_{selected_note_key}"
                )

                mistake_tag = st.selectbox(
                    "Fehler / Problem",
                    [
                        "Kein Fehler",
                        "Zu früher Einstieg",
                        "Zu später Einstieg",
                        "SL verschoben",
                        "Gewinne zu früh genommen",
                        "Zu lange gehalten",
                        "Kein klarer Plan",
                        "Zu große Position",
                        "Gegen Trend gehandelt"
                    ],
                    index=[
                        "Kein Fehler",
                        "Zu früher Einstieg",
                        "Zu später Einstieg",
                        "SL verschoben",
                        "Gewinne zu früh genommen",
                        "Zu lange gehalten",
                        "Kein klarer Plan",
                        "Zu große Position",
                        "Gegen Trend gehandelt"
                    ].index(selected_payload.get("mistake_tag", "Kein Fehler")),
                    key=f"mistake_tag_{selected_note_key}"
                )

            with note_col2:
                emotion_tag = st.selectbox(
                    "Emotion",
                    ["Neutral", "FOMO", "Angst", "Gier", "Unsicherheit", "Stress", "Geduldig"],
                    index=["Neutral", "FOMO", "Angst", "Gier", "Unsicherheit", "Stress", "Geduldig"].index(
                        selected_payload.get("emotion_tag", "Neutral")
                    ),
                    key=f"emotion_tag_{selected_note_key}"
                )

                plan_followed = st.selectbox(
                    "Plan befolgt?",
                    ["Unbekannt", "Ja", "Nein"],
                    index=["Unbekannt", "Ja", "Nein"].index(selected_payload.get("plan_followed", "Unbekannt")),
                    key=f"plan_followed_{selected_note_key}"
                )

            lesson_note = st.text_area(
                "Was war die wichtigste Lektion aus diesem Trade?",
                value=selected_payload.get("lesson_note", ""),
                key=f"lesson_note_{selected_note_key}",
                height=120
            )

            save_col1, save_col2 = st.columns(2)

            with save_col1:
                if st.button("Bewertung speichern", key=f"save_trade_note_{selected_note_key}", width="stretch"):
                    save_trade_note_payload(
                        selected_note_key,
                        {
                            "setup_quality": setup_quality,
                            "mistake_tag": mistake_tag,
                            "emotion_tag": emotion_tag,
                            "lesson_note": lesson_note,
                            "plan_followed": plan_followed
                        }
                    )
                    st.success("Trade-Review gespeichert.")
                    st.rerun()

            with save_col2:
                if st.button("Bewertung zurücksetzen", key=f"reset_trade_note_{selected_note_key}", width="stretch"):
                    save_trade_note_payload(
                        selected_note_key,
                        {
                            "setup_quality": "Nicht bewertet",
                            "mistake_tag": "Kein Fehler",
                            "emotion_tag": "Neutral",
                            "lesson_note": "",
                            "plan_followed": "Unbekannt"
                        }
                    )
                    st.success("Trade-Review zurückgesetzt.")
                    st.rerun()

            with st.expander("📋 Alle Journal-Notizen als Tabelle", expanded=False):
                display_notes_df = journal_notes_df.copy()
                if not display_notes_df.empty and "Zeit" in display_notes_df.columns:
                    display_notes_df["Zeit"] = pd.to_datetime(display_notes_df["Zeit"], errors="coerce").dt.strftime("%d.%m.%Y %H:%M")
                st.dataframe(display_notes_df, width="stretch")

            st.markdown("---")
            st.write("#### Journal verwalten")

            journal_manage_col1, journal_manage_col2 = st.columns(2)

            with journal_manage_col1:
                if st.button("Alle Journal-Notizen speichern", key="save_all_journal_notes_btn", width="stretch"):
                    save_trade_journal_notes(st.session_state.trade_journal_notes)
                    st.success("Alle Journal-Notizen wurden gespeichert.")

            with journal_manage_col2:
                if st.button("Alle Journal-Notizen zurücksetzen", key="reset_all_journal_notes_btn", width="stretch"):
                    st.session_state.trade_journal_notes = {}
                    save_trade_journal_notes(st.session_state.trade_journal_notes)
                    st.success("Alle Journal-Notizen wurden zurückgesetzt.")
                    st.rerun()

    # ========================================================
    # TAB 4 — LEARNING
    # ========================================================
    with paper_tab_learning:

        section_block_start("wide")

        section_header(
            "Learning Dashboard",
            "Hier werden Fehler, Emotionen, Setup-Qualität und dein Lernfortschritt visuell zusammengefasst."
        )

        if 'journal_notes_df' not in locals():
            journal_history_df = build_trade_journal_dataframe()
            journal_review_df = build_closed_trades_review_df(journal_history_df)
            journal_notes_df = build_trade_notes_dataframe(journal_review_df)

        if journal_notes_df.empty:
            st.info("Sobald du Journal-Notizen speicherst, füllt sich dieses Dashboard automatisch.")
        else:
            learning_counts = build_learning_dashboard_counts(journal_notes_df)

            dashboard_col1, dashboard_col2 = st.columns(2)

            with dashboard_col1:
                st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
                mistake_fig = create_learning_bar_figure(
                    learning_counts["mistake_counts"],
                    "Fehler-Verteilung",
                    st.session_state.chart_theme
                )
                st.plotly_chart(mistake_fig, width="stretch", key="learning_mistake_chart")
                st.markdown('</div>', unsafe_allow_html=True)

            with dashboard_col2:
                st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
                emotion_fig = create_learning_bar_figure(
                    learning_counts["emotion_counts"],
                    "Emotions-Verteilung",
                    st.session_state.chart_theme
                )
                st.plotly_chart(emotion_fig, width="stretch", key="learning_emotion_chart")
                st.markdown('</div>', unsafe_allow_html=True)

            dashboard_col3, dashboard_col4 = st.columns(2)

            with dashboard_col3:
                st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
                setup_fig = create_learning_bar_figure(
                    learning_counts["setup_counts"],
                    "Setup-Qualität",
                    st.session_state.chart_theme
                )
                st.plotly_chart(setup_fig, width="stretch", key="learning_setup_chart")
                st.markdown('</div>', unsafe_allow_html=True)

            with dashboard_col4:
                st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
                plan_fig = create_learning_bar_figure(
                    learning_counts["plan_counts"],
                    "Plan befolgt?",
                    st.session_state.chart_theme
                )
                st.plotly_chart(plan_fig, width="stretch", key="learning_plan_chart")
                st.markdown('</div>', unsafe_allow_html=True)

            dashboard_col5, dashboard_col6 = st.columns(2)

            with dashboard_col5:
                st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
                setup_pnl_fig = create_setup_vs_pnl_figure(
                    journal_notes_df,
                    journal_review_df,
                    st.session_state.chart_theme
                )
                st.plotly_chart(setup_pnl_fig, width="stretch", key="learning_setup_vs_pnl_chart")
                st.markdown('</div>', unsafe_allow_html=True)

            with dashboard_col6:
                st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
                cumulative_fig = create_cumulative_realized_pnl_figure(
                    journal_review_df,
                    st.session_state.chart_theme
                )
                st.plotly_chart(cumulative_fig, width="stretch", key="learning_cumulative_pnl_chart")
                st.markdown('</div>', unsafe_allow_html=True)

            highlights = build_learning_dashboard_highlights(journal_notes_df, journal_review_df)
            render_learning_dashboard_highlights(highlights)

        st.markdown("---")
        section_header(
            "Statistik pro Risiko-Profil",
            "Hier siehst du, wie deine geschlossenen Trades je Risiko-Profil abgeschnitten haben."
        )

        risk_profile_history_df = build_risk_profile_history_df()
        risk_profile_review_df = build_risk_profile_review_df(risk_profile_history_df)
        risk_profile_stats_df = calculate_risk_profile_statistics(risk_profile_review_df)

        if risk_profile_stats_df.empty:
            st.info("Noch nicht genug geschlossene Trades mit Risiko-Profil für eine Auswertung.")
        else:
            with st.expander("📋 Tabellenansicht Risiko-Profile", expanded=True):
                st.dataframe(risk_profile_stats_df, width="stretch")

            st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
            risk_profile_fig = create_risk_profile_bar_figure(
                risk_profile_stats_df,
                st.session_state.chart_theme
            )
            st.plotly_chart(
                risk_profile_fig,
                width="stretch",
                key="risk_profile_stats_chart"
            )
            st.markdown('</div>', unsafe_allow_html=True)

            feedback_lines = get_risk_profile_feedback(risk_profile_stats_df)
            for line in feedback_lines:
                panel_note("Profil-Insight", line)

        st.markdown("---")
        section_header(
            "Setup-Statistik",
            "Hier siehst du, welche Setup-Qualitäten und Fehlerbilder in deinen geschlossenen Trades aktuell gut oder schwach laufen."
        )

        setup_stats_df = build_setup_statistics_df(journal_notes_df, journal_review_df)
        mistake_stats_df = build_mistake_statistics_df(journal_notes_df)

        if setup_stats_df.empty:
            st.info("Noch nicht genug Journal-Daten für eine Setup-Statistik.")
        else:
            stats_col1, stats_col2 = st.columns(2)

            with stats_col1:
                with st.expander("📋 Setup-Tabellenansicht", expanded=True):
                    st.dataframe(setup_stats_df, width="stretch")

            with stats_col2:
                with st.expander("📋 Fehler-Tabellenansicht", expanded=True):
                    st.dataframe(mistake_stats_df, width="stretch")

            st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
            setup_fig = create_setup_statistics_figure(
                setup_stats_df,
                st.session_state.chart_theme
            )
            st.plotly_chart(
                setup_fig,
                width="stretch",
                key="setup_statistics_chart"
            )
            st.markdown('</div>', unsafe_allow_html=True)

            if not mistake_stats_df.empty:
                st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
                mistake_fig = create_mistake_statistics_figure(
                    mistake_stats_df,
                    st.session_state.chart_theme
                )
                st.plotly_chart(
                    mistake_fig,
                    width="stretch",
                    key="mistake_statistics_chart"
                )
                st.markdown('</div>', unsafe_allow_html=True)

            feedback_lines = get_setup_statistics_feedback(setup_stats_df)
            for line in feedback_lines:
                panel_note("Setup-Insight", line)

        st.markdown("---")
        section_header(
            "Smart Insights",
            "Die App fasst wiederkehrende Muster aus deinen Trades zusammen und gibt dir Coaching-Hinweise."
        )

        smart_insights = build_smart_insights(
            journal_notes_df=journal_notes_df,
            journal_review_df=journal_review_df,
            risk_profile_stats_df=risk_profile_stats_df if 'risk_profile_stats_df' in locals() else None,
            setup_stats_df=setup_stats_df if 'setup_stats_df' in locals() else None
        )

        smart_actions = build_smart_coaching_actions(
            journal_notes_df=journal_notes_df,
            risk_profile_stats_df=risk_profile_stats_df if 'risk_profile_stats_df' in locals() else None,
            setup_stats_df=setup_stats_df if 'setup_stats_df' in locals() else None
        )

        render_smart_insights_cards(smart_insights, title="Smart Insight")
        render_smart_insights_cards(smart_actions, title="Coaching-Aktion")

        section_block_end()

    # ========================================================
    # TAB 5 — DATEN
    # ========================================================
    with paper_tab_data:

        section_header(
            "Export & Backup",
            "Lade Trades, Journal und wichtige App-Daten als CSV oder JSON herunter."
        )

        trade_history_export_df = build_export_trade_history_df()
        journal_notes_export_df = build_export_journal_notes_df()
        watchlist_export_df = build_export_watchlist_df()
        settings_export_dict = build_export_settings_dict()
        full_backup_dict = build_full_backup_dict()

        export_col1, export_col2 = st.columns(2)

        with export_col1:
            st.download_button(
                "Trade-Historie CSV herunterladen",
                data=dataframe_to_csv_bytes(trade_history_export_df),
                file_name="emanacci_trade_history.csv",
                mime="text/csv",
                key="download_trade_history_csv",
                width="stretch"
            )

            st.download_button(
                "Journal-Notizen CSV herunterladen",
                data=dataframe_to_csv_bytes(journal_notes_export_df),
                file_name="emanacci_journal_notes.csv",
                mime="text/csv",
                key="download_journal_notes_csv",
                width="stretch"
            )

            st.download_button(
                "Watchlist CSV herunterladen",
                data=dataframe_to_csv_bytes(watchlist_export_df),
                file_name="emanacci_watchlist.csv",
                mime="text/csv",
                key="download_watchlist_csv",
                width="stretch"
            )

        with export_col2:
            st.download_button(
                "Settings JSON herunterladen",
                data=dict_to_json_bytes(settings_export_dict),
                file_name="emanacci_settings.json",
                mime="application/json",
                key="download_settings_json",
                width="stretch"
            )

            st.download_button(
                "Journal-Notizen JSON herunterladen",
                data=dict_to_json_bytes(st.session_state.get("trade_journal_notes", {})),
                file_name="emanacci_journal_notes.json",
                mime="application/json",
                key="download_journal_notes_json",
                width="stretch"
            )

            st.download_button(
                "Vollbackup JSON herunterladen",
                data=dict_to_json_bytes(full_backup_dict),
                file_name="emanacci_full_backup.json",
                mime="application/json",
                key="download_full_backup_json",
                width="stretch"
            )

        panel_note(
            "Hinweis",
            "CSV eignet sich gut für Excel oder Google Sheets. JSON ist besser für vollständige Backups deiner App-Daten."
        )

        st.markdown("---")
        section_header(
            "Import / Restore",
            "Lade ein JSON-Backup hoch und stelle ausgewählte Bereiche deiner App wieder her."
        )

        uploaded_backup_file = st.file_uploader(
            "Backup-Datei auswählen",
            type=["json"],
            key="backup_restore_uploader"
        )

        parsed_backup_data = None

        if uploaded_backup_file is not None:
            parsed_backup_data, backup_error = parse_uploaded_backup_json(uploaded_backup_file)

            if backup_error:
                st.error(backup_error)
            else:
                panel_note(
                    "Backup erkannt",
                    "Die Datei wurde erfolgreich gelesen. Du kannst jetzt auswählen, welche Bereiche wiederhergestellt werden sollen."
                )

                preview_lines = build_backup_preview_lines(parsed_backup_data)
                if preview_lines:
                    for line in preview_lines:
                        st.markdown(
                            f"""
                            <div class="em-card">
                                <div class="em-card-title">Backup-Vorschau</div>
                                <div class="em-card-sub">{line}</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                restore_col1, restore_col2 = st.columns(2)

                with restore_col1:
                    restore_settings_toggle = st.checkbox(
                        "Settings wiederherstellen",
                        value=True,
                        key="restore_settings_toggle"
                    )

                    restore_watchlist_toggle = st.checkbox(
                        "Watchlist wiederherstellen",
                        value=True,
                        key="restore_watchlist_toggle"
                    )

                with restore_col2:
                    restore_journal_toggle = st.checkbox(
                        "Journal-Notizen wiederherstellen",
                        value=True,
                        key="restore_journal_toggle"
                    )

                    restore_paper_toggle = st.checkbox(
                        "Paper-Trading-Daten wiederherstellen",
                        value=False,
                        key="restore_paper_toggle"
                    )

                restore_now = st.button(
                    "Ausgewählte Bereiche wiederherstellen",
                    key="restore_backup_now_btn",
                    width="stretch"
                )

                if restore_now:
                    restored_parts = restore_backup_sections(
                        backup_data=parsed_backup_data,
                        restore_settings=restore_settings_toggle,
                        restore_watchlist=restore_watchlist_toggle,
                        restore_journal=restore_journal_toggle,
                        restore_paper_data=restore_paper_toggle
                    )

                    if restored_parts:
                        st.success("Wiederhergestellt: " + ", ".join(restored_parts))
                        st.rerun()
                    else:
                        st.warning("Es wurde kein Bereich zur Wiederherstellung ausgewählt.")

        panel_note(
            "Sicherheitshinweis",
            "Am sichersten ist es, zunächst nur Settings, Watchlist oder Journal-Notizen zu importieren. Paper-Trading-Daten überschreiben bestehende Testdaten."
        )

        st.markdown("---")
        section_header(
            "Datenverwaltung & Reset",
            "Setze einzelne Bereiche gezielt zurück. Kritische Aktionen brauchen eine ausdrückliche Bestätigung."
        )

        panel_note(
            "Sicherheit",
            "Vor einem Reset ist ein Backup sinnvoll. Exportiere deine Daten am besten zuerst über den Export-Bereich."
        )

        with st.expander("Watchlist zurücksetzen", expanded=False):
            st.caption("Entfernt alle Symbole aus deiner aktuellen Watchlist.")
            st.session_state.confirm_reset_watchlist = st.checkbox(
                "Ich möchte die Watchlist wirklich zurücksetzen",
                value=st.session_state.confirm_reset_watchlist,
                key="confirm_reset_watchlist_checkbox"
            )

            if st.button("Watchlist zurücksetzen", key="reset_watchlist_btn", width="stretch"):
                if st.session_state.confirm_reset_watchlist:
                    reset_watchlist_data()
                    st.success("Die Watchlist wurde zurückgesetzt.")
                    st.rerun()
                else:
                    st.warning("Bitte bestätige zuerst die Aktion.")

        with st.expander("Journal-Notizen zurücksetzen", expanded=False):
            st.caption("Löscht alle gespeicherten Trade-Journal-Notizen.")
            st.session_state.confirm_reset_journal = st.checkbox(
                "Ich möchte die Journal-Notizen wirklich zurücksetzen",
                value=st.session_state.confirm_reset_journal,
                key="confirm_reset_journal_checkbox"
            )

            if st.button("Journal zurücksetzen", key="reset_journal_btn", width="stretch"):
                if st.session_state.confirm_reset_journal:
                    reset_journal_data()
                    st.success("Die Journal-Notizen wurden zurückgesetzt.")
                    st.rerun()
                else:
                    st.warning("Bitte bestätige zuerst die Aktion.")

        with st.expander("Paper-Trading-Daten zurücksetzen", expanded=False):
            st.caption("Setzt Cash, Positionen, Orders, Historie und Equity zurück.")
            st.session_state.confirm_reset_paper = st.checkbox(
                "Ich möchte die Paper-Trading-Daten wirklich zurücksetzen",
                value=st.session_state.confirm_reset_paper,
                key="confirm_reset_paper_checkbox"
            )

            if st.button("Paper Trading zurücksetzen", key="reset_paper_btn", width="stretch"):
                if st.session_state.confirm_reset_paper:
                    reset_paper_trading_data()
                    st.success("Die Paper-Trading-Daten wurden zurückgesetzt.")
                    st.rerun()
                else:
                    st.warning("Bitte bestätige zuerst die Aktion.")

        with st.expander("App-Settings zurücksetzen", expanded=False):
            st.caption("Setzt wichtige App-Einstellungen auf Standardwerte zurück.")
            st.session_state.confirm_reset_settings = st.checkbox(
                "Ich möchte die App-Settings wirklich zurücksetzen",
                value=st.session_state.confirm_reset_settings,
                key="confirm_reset_settings_checkbox"
            )

            if st.button("Settings zurücksetzen", key="reset_settings_btn", width="stretch"):
                if st.session_state.confirm_reset_settings:
                    reset_settings_data()
                    st.success("Die App-Settings wurden zurückgesetzt.")
                    st.rerun()
                else:
                    st.warning("Bitte bestätige zuerst die Aktion.")

        with st.expander("Alles zurücksetzen", expanded=False):
            st.caption("Setzt Watchlist, Journal, Paper Trading und Settings komplett zurück.")
            panel_note(
                "Achtung",
                "Das ist die stärkste Reset-Aktion. Bestehende Testdaten und Notizen gehen verloren, wenn du kein Backup gemacht hast."
            )

            st.session_state.confirm_reset_all = st.checkbox(
                "Ich möchte wirklich ALLE App-Daten zurücksetzen",
                value=st.session_state.confirm_reset_all,
                key="confirm_reset_all_checkbox"
            )

            if st.button("Alles zurücksetzen", key="reset_all_btn", width="stretch"):
                if st.session_state.confirm_reset_all:
                    reset_all_app_data()
                    st.success("Alle ausgewählten App-Daten wurden zurückgesetzt.")
                    st.rerun()
                else:
                    st.warning("Bitte bestätige zuerst die Aktion.")

        st.markdown("---")
        section_header(
            "Final Release Check",
            "Prüfe wichtige Datenbereiche und erkenne kleine Probleme vor dem echten Einsatz schneller."
        )

        show_release_checklist = st.toggle(
            "Release-Check anzeigen",
            value=bool(st.session_state.show_release_checklist),
            key="show_release_checklist_toggle"
        )

        if show_release_checklist:
            release_checks = build_release_check_results()
            passed_checks, total_checks = build_release_summary(release_checks)

            summary_col1, summary_col2 = st.columns(2)

            with summary_col1:
                st.metric("Bestandene Checks", f"{passed_checks}/{total_checks}")

            with summary_col2:
                st.metric("Offene Punkte", total_checks - passed_checks)

            render_release_check_cards(release_checks)

            release_feedback = get_release_feedback(release_checks)
            render_release_feedback(release_feedback)

            panel_note(
                "Letzter Feinschliff",
                "Diese Checkliste ersetzt keine vollständigen Tests, hilft aber dabei, offensichtliche Daten- oder UI-Probleme schneller zu sehen."
            )


if interval == "15m" and period not in ["5d", "1mo"]:
    invalid_combo = True

if interval == "1h" and period not in ["5d", "1mo", "3mo", "6mo"]:
    invalid_combo = True

if invalid_combo:
    with tab_analyse:
        st.error("Diese Kombination aus Zeitraum und Intervall ist bei yfinance oft nicht verfügbar.")
    with tab_vergleich:
        st.error("Diese Kombination aus Zeitraum und Intervall ist bei yfinance oft nicht verfügbar.")
else:
    data = load_data(ticker, period, interval)

    if data.empty:
        with tab_analyse:
            st.error("Keine Daten gefunden.")
        with tab_vergleich:
            st.error("Keine Daten für den Vergleich verfügbar.")
    else:
        data = calculate_indicators(data)

        swing_high = data["High"].max()
        swing_low = data["Low"].min()
        fib_range = swing_high - swing_low

        fib_levels = {
            "0.236": swing_high - fib_range * 0.236,
            "0.382": swing_high - fib_range * 0.382,
            "0.500": swing_high - fib_range * 0.500,
            "0.618": swing_high - fib_range * 0.618,
            "0.786": swing_high - fib_range * 0.786,
        }

        supports = []
        resistances = []
        lookback = 2

        for i in range(lookback, len(data) - lookback):
            low = data["Low"].iloc[i]
            high = data["High"].iloc[i]

            if (
                low < data["Low"].iloc[i - 1]
                and low < data["Low"].iloc[i - 2]
                and low < data["Low"].iloc[i + 1]
                and low < data["Low"].iloc[i + 2]
            ):
                supports.append(low)

            if (
                high > data["High"].iloc[i - 1]
                and high > data["High"].iloc[i - 2]
                and high > data["High"].iloc[i + 1]
                and high > data["High"].iloc[i + 2]
            ):
                resistances.append(high)

        supports = filter_levels(supports)
        resistances = filter_levels(resistances)

        supports = supports[-3:]
        resistances = resistances[-3:]

        trades_df, equity_df, buy_df, sell_df = backtest_ema_strategy(
            data,
            initial_capital=1000,
            fee_percent=fee_percent,
            stop_loss_percent=stop_loss_percent,
            take_profit_percent=take_profit_percent,
            use_rsi_filter=use_rsi_filter,
            rsi_min=rsi_min,
            rsi_max=rsi_max,
            use_ema200_filter=use_ema200_filter
        )

        # Zweite Strategie: OHNE RSI Filter
        trades_df_no_rsi, equity_df_no_rsi, _, _ = backtest_ema_strategy(
            data,
            initial_capital=1000,
            fee_percent=fee_percent,
            stop_loss_percent=stop_loss_percent,
            take_profit_percent=take_profit_percent,
            use_rsi_filter=False,
            use_ema200_filter=use_ema200_filter
        )

        with tab_analyse:

            render_help_center()
            
            section_block_start("wide")
            render_hero(
                "Analyse",
                "Hier verstehst du Trend, Preiszonen und mögliche Setups in einer klaren, anfängerfreundlichen Oberfläche."
            )
            section_block_end()

            section_header(
                "Schneller Überblick",
                "Nutze zuerst Trend, Preis und wichtige Zonen. Detaillierte Indikatoren findest du im Tab Advanced."
            )

            render_analysis_learning_cards()

            snapshot = get_analysis_snapshot(data)
            learning_signal = build_learning_signal(snapshot, supports, resistances)
            trade_idea = build_trade_idea(snapshot, supports, resistances)

            render_analysis_snapshot_metrics(snapshot)
            render_analysis_indicator_cards(snapshot, supports, resistances)

            with st.expander("ℹ️ Begriffe kurz erklärt", expanded=False):
                st.write("""
                **EMA** zeigt den gleitenden Durchschnitt des Kurses und hilft beim Erkennen des Trends.  
                **Fibonacci** markiert mögliche Preiszonen, an denen der Kurs reagieren kann.  
                **Support / Resistance** sind Bereiche, in denen Käufer oder Verkäufer häufiger aktiv werden.  
                **RSI** hilft einzuschätzen, ob der Markt eher stark gelaufen ist.  
                **Stop-Loss / Take-Profit** helfen dir, Verluste zu begrenzen und Gewinne zu sichern.
                """)

            section_header(
                "Positionsstatus",
                "Hier siehst du sofort, ob für das aktuelle Symbol bereits eine Paper-Trading-Position offen ist."
            )
            render_analysis_position_card(ticker)

            ui_gap("sm")

            section_header(
                "Lernhilfe & Trade-Idee",
                "Diese Hinweise sind bewusst einfach formuliert und sollen dir helfen, Marktstruktur besser einzuordnen."
            )

            smart_col1, smart_col2 = st.columns(2)

            with smart_col1:
                render_learning_signal_box(learning_signal)

            with smart_col2:
                render_trade_idea_box(trade_idea, ticker)

            render_trade_idea_quick_actions(ticker, trade_idea)

            ui_gap("sm")

            section_block_start("wide")

            section_header(
                "Chart",
                "Kerzenchart mit Trendlinien, Preiszonen und optionalen Markern für Backtest und Paper Trading."
            )

            chart_summary_col1, chart_summary_col2, chart_summary_col3, chart_summary_col4 = st.columns(4)

            with chart_summary_col1:
                st.metric("Kerzen", len(data))

            with chart_summary_col2:
                st.metric("Letzter Close", f"{float(data['Close'].iloc[-1]):.2f} €")

            with chart_summary_col3:
                st.metric("Supports", len(supports))

            with chart_summary_col4:
                st.metric("Resistances", len(resistances))

            analysis_chart_fig = create_analysis_chart_figure(
                data=data,
                ticker=ticker,
                chart_theme=st.session_state.chart_theme,
                show_ema=st.session_state.show_ema,
                show_fibonacci=st.session_state.show_fibonacci,
                show_support_resistance=st.session_state.show_support_resistance,
                show_volume=st.session_state.show_volume,
                show_trade_markers=st.session_state.show_trade_markers,
                show_paper_markers=st.session_state.get("show_paper_markers", True),
                show_sl_tp_orders=st.session_state.get("show_sl_tp_orders", True),
                supports=supports,
                resistances=resistances,
                buy_df=buy_df,
                sell_df=sell_df
            )

            st.markdown('<div class="em-chart-container">', unsafe_allow_html=True)
            st.plotly_chart(
                analysis_chart_fig,
                width="stretch",
                key="analysis_chart_main_release"
            )
            st.markdown('</div>', unsafe_allow_html=True)

            section_block_end()

            panel_note(
                "Hinweis",
                "Der Analyse-Tab bleibt bewusst einfach. RSI, MACD, Backtesting und Strategie-Vergleich findest du im Tab Advanced."
            )

        with tab_advanced:
            render_advanced_intro()
            render_advanced_top_metrics(data)

            with st.expander("ℹ️ Was zeigt dir der Advanced-Tab?", expanded=False):
                st.write("""
                **RSI** zeigt, ob ein Markt eher stark gestiegen oder gefallen ist.  
                **MACD** hilft dir, Trendwechsel und Momentum besser zu erkennen.  
                **Backtesting** zeigt, wie eine Strategie in historischen Daten abgeschnitten hätte.  
                **Strategie-Vergleich** hilft dir, mehrere Ansätze nebeneinander zu sehen.
                """)

            st.markdown("---")
            # ---------------- RSI ----------------
            st.write("### RSI")
            st.caption("Der RSI hilft dir einzuschätzen, ob ein Markt eher überkauft oder überverkauft ist.")

            rsi_fig = create_rsi_figure(data, st.session_state.chart_theme)
            st.plotly_chart(rsi_fig, width="stretch", key="advanced_rsi_chart_clean")

            # ---------------- MACD ----------------
            st.write("### MACD")
            st.caption("Der MACD zeigt Trendstärke und mögliche Richtungswechsel.")

            macd_fig = create_macd_figure(data, st.session_state.chart_theme)
            st.plotly_chart(macd_fig, width="stretch", key="advanced_macd_chart_clean")

            # ---------------- BACKTESTING ----------------
            st.write("### Backtesting")
            st.caption("Teste hier deine EMA-Strategie mit den aktuellen Parametern auf historischen Daten.")

            bt_col1, bt_col2, bt_col3, bt_col4 = st.columns(4)

            with bt_col1:
                bt_initial_capital = st.number_input(
                    "Startkapital",
                    min_value=100.0,
                    value=float(st.session_state.get("initial_capital", 1000.0)),
                    step=100.0,
                    key="advanced_bt_initial_capital"
                )

            with bt_col2:
                bt_fee_percent = st.number_input(
                    "Gebühr (%)",
                    min_value=0.0,
                    value=float(st.session_state.fee_percent),
                    step=0.01,
                    key="advanced_bt_fee_percent"
                )

            with bt_col3:
                bt_stop_loss_percent = st.number_input(
                    "Stop-Loss (%)",
                    min_value=0.0,
                    value=float(st.session_state.stop_loss_percent),
                    step=0.5,
                    key="advanced_bt_stop_loss_percent"
                )

            with bt_col4:
                bt_take_profit_percent = st.number_input(
                    "Take-Profit (%)",
                    min_value=0.0,
                    value=float(st.session_state.take_profit_percent),
                    step=0.5,
                    key="advanced_bt_take_profit_percent"
                )

            bt_col5, bt_col6, bt_col7 = st.columns(3)

            with bt_col5:
                bt_use_rsi_filter = st.checkbox(
                    "RSI Filter nutzen",
                    value=bool(st.session_state.use_rsi_filter),
                    key="advanced_bt_use_rsi_filter"
                )

            with bt_col6:
                bt_rsi_min = st.number_input(
                    "RSI Min",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.rsi_min),
                    step=1.0,
                    key="advanced_bt_rsi_min"
                )

            with bt_col7:
                bt_rsi_max = st.number_input(
                    "RSI Max",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.rsi_max),
                    step=1.0,
                    key="advanced_bt_rsi_max"
                )

            bt_use_ema200_filter = st.checkbox(
                "EMA200 Filter nutzen",
                value=bool(st.session_state.use_ema200_filter),
                key="advanced_bt_use_ema200_filter"
            )

            run_backtest_now = st.button("Backtest ausführen", key="advanced_run_backtest", width="stretch")

            if run_backtest_now:
                advanced_trades_df, advanced_equity_df, advanced_buy_df, advanced_sell_df = backtest_ema_strategy(
                    data=data,
                    initial_capital=bt_initial_capital,
                    fee_percent=bt_fee_percent,
                    stop_loss_percent=bt_stop_loss_percent,
                    take_profit_percent=bt_take_profit_percent,
                    use_rsi_filter=bt_use_rsi_filter,
                    rsi_min=bt_rsi_min,
                    rsi_max=bt_rsi_max,
                    use_ema200_filter=bt_use_ema200_filter
                )

                st.session_state.advanced_trades_df = advanced_trades_df
                st.session_state.advanced_equity_df = advanced_equity_df
                st.session_state.advanced_buy_df = advanced_buy_df
                st.session_state.advanced_sell_df = advanced_sell_df
                st.session_state.advanced_bt_initial_capital_used = bt_initial_capital

            if "advanced_trades_df" in st.session_state and "advanced_equity_df" in st.session_state:
                advanced_trades_df = st.session_state.advanced_trades_df
                advanced_equity_df = st.session_state.advanced_equity_df
                bt_initial_capital_used = float(st.session_state.get("advanced_bt_initial_capital_used", bt_initial_capital))

                advanced_summary = calc_backtest_summary(
                    trades_df=advanced_trades_df,
                    equity_df=advanced_equity_df,
                    initial_capital=bt_initial_capital_used
                )

                render_backtest_metrics(advanced_summary)

                if not advanced_equity_df.empty:
                    backtest_compare_fig = create_equity_comparison_figure(
                        [{"name": "EMA Strategie", "equity_df": advanced_equity_df, "trades_df": advanced_trades_df}],
                        st.session_state.chart_theme
                    )
                    st.plotly_chart(
                        backtest_compare_fig,
                        width="stretch",
                        key="advanced_backtest_equity_single"
                    )

                with st.expander("📋 Backtest Trades", expanded=False):
                    st.dataframe(advanced_trades_df, width="stretch")

                # ---------------- STRATEGIE VERGLEICH ----------------
                st.write("### Strategie-Vergleich")
                st.caption("Vergleiche einfache Strategien nebeneinander, um Unterschiede bei Return, Risiko und Trefferquote zu sehen.")

                compare_initial_capital = float(st.session_state.get("initial_capital", 1000.0))
                compare_fee_percent = float(st.session_state.fee_percent)
                compare_stop_loss_percent = float(st.session_state.stop_loss_percent)
                compare_take_profit_percent = float(st.session_state.take_profit_percent)

                strategy_1_trades, strategy_1_equity, _, _ = backtest_ema_strategy(
                    data=data,
                    initial_capital=compare_initial_capital,
                    fee_percent=compare_fee_percent,
                    stop_loss_percent=compare_stop_loss_percent,
                    take_profit_percent=compare_take_profit_percent,
                    use_rsi_filter=False,
                    rsi_min=0.0,
                    rsi_max=100.0,
                    use_ema200_filter=False
                )

                strategy_2_trades, strategy_2_equity, _, _ = backtest_ema_strategy(
                    data=data,
                    initial_capital=compare_initial_capital,
                    fee_percent=compare_fee_percent,
                    stop_loss_percent=compare_stop_loss_percent,
                    take_profit_percent=compare_take_profit_percent,
                    use_rsi_filter=True,
                    rsi_min=float(st.session_state.rsi_min),
                    rsi_max=float(st.session_state.rsi_max),
                    use_ema200_filter=False
                )

                strategy_3_trades, strategy_3_equity, _, _ = backtest_ema_strategy(
                    data=data,
                    initial_capital=compare_initial_capital,
                    fee_percent=compare_fee_percent,
                    stop_loss_percent=compare_stop_loss_percent,
                    take_profit_percent=compare_take_profit_percent,
                    use_rsi_filter=True,
                    rsi_min=float(st.session_state.rsi_min),
                    rsi_max=float(st.session_state.rsi_max),
                    use_ema200_filter=True
                )

                strategy_results = [
                    {
                        "name": "EMA Cross",
                        "trades_df": strategy_1_trades,
                        "equity_df": strategy_1_equity
                    },
                    {
                        "name": "EMA + RSI",
                        "trades_df": strategy_2_trades,
                        "equity_df": strategy_2_equity
                    },
                    {
                        "name": "EMA + RSI + EMA200",
                        "trades_df": strategy_3_trades,
                        "equity_df": strategy_3_equity
                    }
                ]

                strategy_summary_df = create_strategy_summary_dataframe(strategy_results, compare_initial_capital)
                st.dataframe(strategy_summary_df, width="stretch")

                strategy_compare_fig = create_equity_comparison_figure(strategy_results, st.session_state.chart_theme)
                st.plotly_chart(
                    strategy_compare_fig,
                    width="stretch",
                    key="advanced_strategy_compare_equity"
                )


        # ---------------- VERGLEICH ----------------
        render_compare_intro()

        compare_top_col1, compare_top_col2 = st.columns([1.5, 1.0])

        with compare_top_col1:
            compare_text = st.text_input(
                "Symbole vergleichen",
                value=st.session_state.get("compare_input", "TSLA, AAPL, NVDA"),
                key="compare_input_clean",
                help="Mehrere Symbole mit Komma trennen, z. B. TSLA, AAPL, NVDA, BTC-USD"
            )

        with compare_top_col2:
            compare_limit = st.selectbox(
                "Max. Karten",
                [4, 6, 8, 10],
                index=1,
                key="compare_limit_cards"
            )

        compare_symbols = parse_compare_symbols(st.session_state.compare_input_clean)

        if len(compare_symbols) < 2:
            st.info("Bitte mindestens zwei Symbole eingeben, damit ein Vergleich sinnvoll ist.")
        else:
            compare_df, compare_chart_df = build_compare_dataset(
                symbols=compare_symbols,
                period=st.session_state.period,
                interval=st.session_state.interval
            )

            if compare_df.empty:
                st.warning("Für die eingegebenen Symbole konnten keine Vergleichsdaten geladen werden.")
            else:
                render_compare_summary_metrics(compare_df)

                st.write("### Vergleichs-Chart")
                st.caption("Alle Symbole werden ab dem ersten verfügbaren Punkt auf 0% normiert.")

                if not compare_chart_df.empty:
                    compare_fig = create_compare_performance_figure(compare_chart_df, st.session_state.chart_theme)
                    st.plotly_chart(compare_fig, width="stretch", key="compare_tab_performance_chart")
                else:
                    st.warning("Chart-Daten für den Vergleich konnten nicht erstellt werden.")

                st.write("### Überblick")
                st.caption("Schneller Überblick über Performance, Trend und RSI.")

                render_compare_cards(compare_df.head(compare_limit))

                with st.expander("📋 Tabellenansicht Vergleich", expanded=False):
                    st.dataframe(compare_df, width="stretch")
