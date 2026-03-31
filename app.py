import pandas as pd
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

    if held_qty < quantity:
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
            increasing_line_color=colors["up_color"],
            decreasing_line_color=colors["down_color"]
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
        paper_bgcolor=colors["paper_bgcolor"],
        plot_bgcolor=colors["plot_bgcolor"],
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

    fig.update_xaxes(gridcolor=colors["grid_color"])
    fig.update_yaxes(gridcolor=colors["grid_color"], title_text="Preis (€)", row=1, col=1)

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
    fig.update_xaxes(gridcolor=colors["grid_color"])
    fig.update_yaxes(gridcolor=colors["grid_color"], range=[0, 100])

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
    fig.update_xaxes(gridcolor=colors["grid_color"])
    fig.update_yaxes(gridcolor=colors["grid_color"])

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
    fig.update_xaxes(gridcolor=colors["grid_color"])
    fig.update_yaxes(gridcolor=colors["grid_color"])

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
    fig.update_xaxes(gridcolor=colors["grid_color"])
    fig.update_yaxes(gridcolor=colors["grid_color"])

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

render_watchlist_intro()

manage_col1, manage_col2 = st.columns([1.4, 1.0])

with manage_col1:
    watchlist_new_symbol = st.text_input(
        "Neues Symbol hinzufügen",
        value="",
        key="watchlist_new_symbol_input",
        help="Zum Beispiel TSLA, AAPL, NVDA, BTC-USD"
    ).upper().strip()

with manage_col2:
    add_watchlist_symbol = st.button(
        "Zur Watchlist hinzufügen",
        key="watchlist_add_symbol_btn",
        width="stretch"
    )

if add_watchlist_symbol:
    if not watchlist_new_symbol:
        st.warning("Bitte zuerst ein Symbol eingeben.")
    elif watchlist_new_symbol in st.session_state.watchlist:
        st.info("Dieses Symbol ist bereits in deiner Watchlist.")
    else:
        st.session_state.watchlist.append(watchlist_new_symbol)
        save_watchlist(st.session_state.watchlist)
        st.success(f"{watchlist_new_symbol} wurde hinzugefügt.")
        st.rerun()

watchlist_df = build_watchlist_snapshot(
    st.session_state.watchlist,
    period="1mo",
    interval="1d"
)

if watchlist_df.empty:
    st.info("Deine Watchlist ist aktuell leer oder es konnten keine Daten geladen werden.")
else:
    render_watchlist_summary_metrics(watchlist_df)

    st.write("### Deine Watchlist")
    st.caption("Schneller Überblick über Preis, Trend, RSI und Performance.")

    watchlist_records = watchlist_df.to_dict("records")

    for i in range(0, len(watchlist_records), 2):
        col1, col2 = st.columns(2)

        with col1:
            render_single_watchlist_card(watchlist_records[i])

        if i + 1 < len(watchlist_records):
            with col2:
                render_single_watchlist_card(watchlist_records[i + 1])

    with st.expander("📋 Tabellenansicht Watchlist", expanded=False):
        st.dataframe(watchlist_df, width="stretch")

with tab_paper:
    st.markdown("""
    <div class="em-section">
        <div class="em-kicker">Paper Trading</div>
        <div><strong>Virtuell handeln und lernen</strong></div>
        <div style="opacity:0.8; margin-top:0.25rem;">
            Hier kannst du ohne echtes Geld üben. Für den Einstieg reicht ein einfacher Kauf oder Verkauf.
            Erweiterte Ordertypen wie Limit, Stop-Loss oder Trailing Stop findest du weiter unten.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info("Einfach starten: Symbol wählen → Stückzahl festlegen → virtuell kaufen. Erweiterte Orders kannst du später nutzen.")

    st.markdown("""
    <div class="em-section">
        <div class="em-kicker">Paper Trading</div>
        <div><strong>Virtuelles Depot, Orders, Equity Curve und Benchmark-Vergleich</strong></div>
        <div style="opacity:0.8; margin-top:0.25rem;">
            Hier testest du deine Trades mit Spielgeld und vergleichst sie mit Buy & Hold.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.write("## Paper Trading")
    st.write("### Einfach handeln")
    st.caption("Für Anfänger: direkt kaufen oder verkaufen – wahlweise nach Stückzahl oder nach Betrag.")

    simple_current_price, simple_trade_time = get_latest_price_for_symbol(ticker)

    if simple_current_price is None:
        st.warning("Kein aktueller Preis für dieses Symbol verfügbar.")
    else:
        simple_fee_rate = st.session_state.fee_percent / 100

        top_col1, top_col2, top_col3 = st.columns([1.1, 1.1, 1.2])

        with top_col1:
            st.radio(
                "Modus",
                ["Stückzahl", "Betrag (€)"],
                key="simple_trade_mode",
                horizontal=True
            )

        with top_col2:
            if st.session_state.simple_trade_mode == "Stückzahl":
                st.number_input(
                    "Stückzahl",
                    min_value=1,
                    value=st.session_state.simple_trade_qty,
                    step=1,
                    key="simple_trade_qty",
                    help="Wie viele Stück du kaufen oder verkaufen möchtest."
                )
            else:
                st.number_input(
                    "Betrag (€)",
                    min_value=1.0,
                    value=st.session_state.simple_trade_amount,
                    step=50.0,
                    key="simple_trade_amount",
                    help="Wie viel Geld du investieren oder verkaufen möchtest."
                )

        ticker_position = st.session_state.paper_positions.get(ticker, {})
        held_qty = int(ticker_position.get("quantity", 0))

        preview_buy_qty, preview_buy_gross, preview_buy_fee, preview_buy_total = calculate_buy_quantity_from_input(
            mode=st.session_state.simple_trade_mode,
            current_price=simple_current_price,
            fee_rate=simple_fee_rate,
            quantity_value=st.session_state.simple_trade_qty,
            amount_value=st.session_state.simple_trade_amount,
            available_cash=st.session_state.paper_cash
        )

        preview_sell_qty = calculate_sell_quantity_from_input(
            mode=st.session_state.simple_trade_mode,
            current_price=simple_current_price,
            quantity_value=st.session_state.simple_trade_qty,
            amount_value=st.session_state.simple_trade_amount,
            held_qty=held_qty
        )

        with top_col3:
            st.markdown(
                f'''
                <div class="em-card">
                    <div class="em-card-title">{ticker}</div>
                    <div class="em-card-sub">Aktueller Preis: {simple_current_price:.2f} €</div>
                    <div class="em-card-sub">Kaufbar: {preview_buy_qty} Stück</div>
                    <div class="em-card-sub">Verkaufbar: {preview_sell_qty} Stück</div>
                    <div class="em-card-sub">Geschätzte Gebühren: {preview_buy_fee:.2f} €</div>
                    <div class="em-card-sub">Verfügbarer Cash: {st.session_state.paper_cash:,.2f} €</div>
                    <div class="em-card-sub">Gehaltene Stück: {held_qty}</div>
                </div>
                ''',
                unsafe_allow_html=True
            )

        action_col1, action_col2, action_col3 = st.columns(3)

        with action_col1:
            simple_buy = st.button("🟢 Kaufen", key="simple_buy_button", width="stretch")

        with action_col2:
            simple_sell = st.button("🟣 Verkaufen", key="simple_sell_button", width="stretch")

        with action_col3:
            simple_sell_all = st.button("🔴 Alles verkaufen", key="simple_sell_all_button", width="stretch")

        if simple_buy:
            quantity, _, _, _ = calculate_buy_quantity_from_input(
                mode=st.session_state.simple_trade_mode,
                current_price=simple_current_price,
                fee_rate=simple_fee_rate,
                quantity_value=st.session_state.simple_trade_qty,
                amount_value=st.session_state.simple_trade_amount,
                available_cash=st.session_state.paper_cash
            )

            success, message = execute_market_buy(
                symbol=ticker,
                quantity=quantity,
                current_price=simple_current_price,
                trade_time=simple_trade_time,
                fee_rate=simple_fee_rate
            )

            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

        if simple_sell:
            quantity = calculate_sell_quantity_from_input(
                mode=st.session_state.simple_trade_mode,
                current_price=simple_current_price,
                quantity_value=st.session_state.simple_trade_qty,
                amount_value=st.session_state.simple_trade_amount,
                held_qty=held_qty
            )

            success, message = execute_market_sell(
                symbol=ticker,
                quantity=quantity,
                current_price=simple_current_price,
                trade_time=simple_trade_time,
                fee_rate=simple_fee_rate
            )

            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

        if simple_sell_all:
            if held_qty < 1:
                st.error("Keine Position vorhanden.")
            else:
                success, message = execute_market_sell(
                    symbol=ticker,
                    quantity=held_qty,
                    current_price=simple_current_price,
                    trade_time=simple_trade_time,
                    fee_rate=simple_fee_rate
                )

                if success:
                    st.success(f"Alle Stück von {ticker} wurden virtuell verkauft.")
                    st.rerun()
                else:
                    st.error(message)
    st.caption("Virtuelles Depot mit Spielgeld, offenen Positionen, Historie und Benchmark-Vergleich.")

    cash = st.session_state.paper_cash
    positions = st.session_state.paper_positions
    history = st.session_state.paper_history

    # ---------------- DEPOT ÜBERSICHT ----------------
    total_positions_value = 0.0
    position_rows = []

    if positions:
        for symbol, pos in positions.items():
            try:
                pos_data = load_data(symbol, period="5d", interval="1d")

                if not pos_data.empty and "Close" in pos_data.columns:
                    current_price = float(pos_data["Close"].iloc[-1])
                else:
                    current_price = pos["avg_price"]

            except Exception:
                current_price = pos["avg_price"]

            quantity = pos["quantity"]
            avg_price = pos["avg_price"]
            total_cost = pos.get("total_cost", quantity * avg_price)

            market_value = quantity * current_price
            open_pnl = market_value - total_cost
            open_pnl_pct = (open_pnl / total_cost * 100) if total_cost > 0 else 0

            total_positions_value += market_value

            position_rows.append({
                "Symbol": symbol,
                "Stück": quantity,
                "Ø Kaufpreis": round(avg_price, 2),
                "Aktueller Preis": round(current_price, 2),
                "Einstand gesamt": round(total_cost, 2),
                "Marktwert": round(market_value, 2),
                "Offener PnL": round(open_pnl, 2),
                "Offener PnL %": round(open_pnl_pct, 2)
            })

    total_portfolio_value = cash + total_positions_value
    total_pnl = total_portfolio_value - st.session_state.paper_start_cash
    total_pnl_pct = (
        total_pnl / st.session_state.paper_start_cash * 100
        if st.session_state.paper_start_cash > 0 else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Cash", f"{cash:,.2f} €")
    c2.metric("📦 Positionswert", f"{total_positions_value:,.2f} €")
    c3.metric("🏦 Gesamtwert", f"{total_portfolio_value:,.2f} €")
    c4.metric("📈 Gesamt-PnL", f"{total_pnl:,.2f} €", f"{total_pnl_pct:.2f}%")

    st.markdown("---")

    st.caption(f"Aktives Symbol für Paper Trading: {ticker}")

    # ---------------- OFFENE POSITIONEN ----------------
    st.write("### Offene Positionen")
    st.caption("Hier siehst du deine aktuellen Positionen mit schnellem Teilverkauf oder vollständigem Schließen.")

    position_rows, total_positions_value = build_paper_positions_snapshot()

    if position_rows:
        render_position_summary_metrics(position_rows, total_positions_value)

        st.markdown("")

        for i in range(0, len(position_rows), 2):
            grid_col1, grid_col2 = st.columns(2)

            with grid_col1:
                render_position_card(position_rows[i])

            if i + 1 < len(position_rows):
                with grid_col2:
                    render_position_card(position_rows[i + 1])

        with st.expander("📋 Tabellenansicht offene Positionen", expanded=False):
            positions_df = pd.DataFrame([
                {
                    "Symbol": row["Symbol"],
                    "Stück": row["Stück"],
                    "Ø Kaufpreis": row["Ø Kaufpreis"],
                    "Aktueller Preis": row["Aktueller Preis"],
                    "Einstand gesamt": row["Einstand gesamt"],
                    "Marktwert": row["Marktwert"],
                    "Offener PnL": row["Offener PnL"],
                    "Offener PnL %": row["Offener PnL %"]
                }
                for row in position_rows
            ])
            st.dataframe(positions_df, width="stretch")
    else:
        st.info("Noch keine offenen Positionen.")

    # ---------------- EQUITY CURVE ----------------
    st.write("### Equity Curve")
    st.caption("Hier siehst du, wie sich dein virtuelles Depot über die Zeit entwickelt hat.")

    equity_df = build_equity_history_dataframe()

    if not equity_df.empty:
        render_equity_metrics(equity_df)

        equity_fig = create_equity_curve_figure(equity_df)
        st.plotly_chart(equity_fig, width="stretch", key="paper_equity_curve_clean")

        with st.expander("📋 Tabellenansicht Equity Curve", expanded=False):
            display_equity_df = equity_df.copy()
            display_equity_df["Zeit"] = pd.to_datetime(
                display_equity_df["Zeit"], errors="coerce"
            ).dt.strftime("%d.%m.%Y %H:%M")
            st.dataframe(display_equity_df, width="stretch")
    else:
        st.info("Noch keine Equity-Daten vorhanden. Führe zuerst ein paar virtuelle Trades aus.")

    # ---------------- BENCHMARK ----------------
    st.write("### Benchmark Vergleich")
    st.caption("Vergleiche dein Paper Trading mit einem bekannten Markt oder einem eigenen Symbol.")

    benchmark_col1, benchmark_col2 = st.columns([1.1, 1.2])

    with benchmark_col1:
        selected_benchmark_option = st.selectbox(
            "Benchmark",
            get_benchmark_options(),
            key="paper_benchmark_option"
        )

    with benchmark_col2:
        if selected_benchmark_option == "Custom":
            benchmark_symbol = st.text_input(
                "Custom Symbol",
                value="MSFT",
                key="paper_benchmark_custom"
            ).upper().strip()
        else:
            benchmark_symbol = selected_benchmark_option

    if not equity_df.empty and benchmark_symbol:
        benchmark_df = load_benchmark_series(benchmark_symbol, period="6mo", interval="1d")

        if benchmark_df.empty:
            st.warning(f"Für {benchmark_symbol} konnten keine Benchmark-Daten geladen werden.")
        else:
            compare_df = merge_equity_with_benchmark(equity_df, benchmark_df)

            if compare_df.empty:
                st.warning("Benchmark-Vergleich konnte nicht erstellt werden.")
            else:
                latest_paper_return = float(compare_df["Return %"].iloc[-1])
                latest_benchmark_return = float(compare_df["Benchmark Return %"].iloc[-1])
                relative_outperformance = latest_paper_return - latest_benchmark_return

                comp_col1, comp_col2, comp_col3 = st.columns(3)

                with comp_col1:
                    st.metric("Paper Trading", f"{latest_paper_return:.2f}%")

                with comp_col2:
                    st.metric(benchmark_symbol, f"{latest_benchmark_return:.2f}%")

                with comp_col3:
                    st.metric("Outperformance", f"{relative_outperformance:.2f}%")

                benchmark_fig = create_benchmark_comparison_figure(compare_df, benchmark_symbol)
                st.plotly_chart(
                    benchmark_fig,
                    width="stretch" ,
                    key="paper_benchmark_comparison_clean"
                )

                with st.expander("📋 Tabellenansicht Benchmark Vergleich", expanded=False):
                    display_compare_df = compare_df.copy()
                    display_compare_df["Zeit"] = pd.to_datetime(
                        display_compare_df["Zeit"], errors="coerce"
                    ).dt.strftime("%d.%m.%Y %H:%M")
                    st.dataframe(
                        display_compare_df[
                            ["Zeit", "Gesamtwert", "Return %", "Benchmark Close", "Benchmark Return %"]
                        ],
                        width="stretch"
                    )
    else:
        st.info("Für den Benchmark-Vergleich werden Equity-Daten aus deinem Paper Trading benötigt.")

    st.write("### Offene Orders")
    st.caption("Hier siehst du alle aktiven Orders. Schutz-Orders stehen oben, Limit-Orders darunter.")

    orders_snapshot = build_open_orders_snapshot()

    if orders_snapshot:
        render_open_orders_summary(orders_snapshot)

        st.markdown("")

        for i in range(0, len(orders_snapshot), 2):
            order_col1, order_col2 = st.columns(2)

            with order_col1:
                render_single_order_card(orders_snapshot[i])

            if i + 1 < len(orders_snapshot):
                with order_col2:
                    render_single_order_card(orders_snapshot[i + 1])

        action_col1, action_col2 = st.columns([1, 2])

        with action_col1:
            if st.button("🗑 Alle Orders löschen", key="cancel_all_orders_clean", width="stretch"):
                st.session_state.paper_open_orders = []
                st.success("Alle offenen Orders wurden gelöscht.")
                st.rerun()

        with st.expander("📋 Tabellenansicht offene Orders", expanded=False):
            open_orders_df = pd.DataFrame([
                {
                    "Order Type": order["Order Type"],
                    "Symbol": order["Symbol"],
                    "Stück": order["Stück"],
                    "Limit Price": order["Limit Price"],
                    "Anchor Price": order["Anchor Price"],
                }
                for order in orders_snapshot
            ])
            st.dataframe(open_orders_df, width="stretch")
    else:
        st.info("Keine offenen Orders vorhanden.")

    # ---------------- HISTORIE ----------------
    st.write("### Trade Historie")
    st.caption("Hier siehst du deine bisherigen virtuellen Trades – mit Filtern, Kennzahlen und Detailansicht.")

    history_df = build_trade_history_dataframe()

    if not history_df.empty:
        filter_col1, filter_col2, filter_col3 = st.columns([1.2, 1.2, 0.8])

        available_symbols = ["Alle"] + sorted(history_df["Symbol"].dropna().astype(str).unique().tolist())
        available_types = ["Alle"] + sorted(history_df["Typ"].dropna().astype(str).unique().tolist())

        with filter_col1:
            selected_history_symbol = st.selectbox(
                "Symbol filtern",
                available_symbols,
                key="history_filter_symbol"
            )

        with filter_col2:
            selected_history_type = st.selectbox(
                "Typ filtern",
                available_types,
                key="history_filter_type"
            )

        with filter_col3:
            max_cards = st.selectbox(
                "Karten",
                [4, 6, 8, 10],
                index=1,
                key="history_filter_card_count"
            )

        filtered_history_df = history_df.copy()

        if selected_history_symbol != "Alle":
            filtered_history_df = filtered_history_df[
                filtered_history_df["Symbol"].astype(str) == selected_history_symbol
            ]

        if selected_history_type != "Alle":
            filtered_history_df = filtered_history_df[
                filtered_history_df["Typ"].astype(str) == selected_history_type
            ]

        render_trade_history_metrics(filtered_history_df)

        st.markdown("")

        recent_cards_df = filtered_history_df.head(max_cards).copy()
        recent_cards_records = recent_cards_df.to_dict("records")

        if recent_cards_records:
            for i in range(0, len(recent_cards_records), 2):
                hist_col1, hist_col2 = st.columns(2)

                with hist_col1:
                    render_trade_history_card(recent_cards_records[i], i)

                if i + 1 < len(recent_cards_records):
                    with hist_col2:
                        render_trade_history_card(recent_cards_records[i + 1], i + 1)

        with st.expander("📋 Tabellenansicht Trade Historie", expanded=False):
            display_history_df = filtered_history_df.copy()

            if "Zeit" in display_history_df.columns:
                display_history_df["Zeit"] = pd.to_datetime(
                    display_history_df["Zeit"], errors="coerce"
                ).dt.strftime("%d.%m.%Y %H:%M")

            st.dataframe(display_history_df, width="stretch")
    else:
        st.info("Noch keine Trades in der Historie vorhanden.")

    # ---------------- RESET ----------------
    st.write("### 🛠 Aktionen")

    if st.button("🗑 Paper Trading zurücksetzen"):
        st.session_state.paper_cash = st.session_state.paper_start_cash
        st.session_state.paper_positions = {}
        st.session_state.paper_history = []
        st.session_state.paper_open_orders = []

        st.session_state.paper_equity_history = [{
            "Zeit": datetime.now(),
            "Cash": st.session_state.paper_start_cash,
            "Positionswert": 0.0,
            "Gesamtwert": st.session_state.paper_start_cash
        }]

        st.success("Paper Trading wurde zurückgesetzt.")
        st.toast("Paper Trading wurde zurückgesetzt.")
        st.rerun()

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
            render_analysis_intro_box()
            render_analysis_learning_cards()

            snapshot = get_analysis_snapshot(data)
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

            render_analysis_position_card(ticker)

            st.markdown("---")

            if ticker in st.session_state.paper_positions:
                pos = st.session_state.paper_positions[ticker]

                current_price = float(data["Close"].iloc[-1])
                quantity = pos["quantity"]
                avg_price = pos["avg_price"]
                total_cost = pos.get("total_cost", quantity * avg_price)

                market_value = quantity * current_price
                open_pnl = market_value - total_cost
                open_pnl_pct = (open_pnl / total_cost * 100) if total_cost > 0 else 0

                p1, p2, p3, p4, p5 = st.columns(5)
                p1.metric("Symbol", ticker)
                p2.metric("Stück", f"{quantity}")
                p3.metric("Ø Kaufpreis", f"{avg_price:.2f} €")
                p4.metric("Aktueller Preis", f"{current_price:.2f} €")
                p5.metric("Offener PnL", f"{open_pnl:.2f} €", f"{open_pnl_pct:.2f}%")

                if open_pnl > 0:
                    st.success(f"Position im Gewinn: {open_pnl:.2f} €")
                elif open_pnl < 0:
                    st.warning(f"Position im Verlust: {open_pnl:.2f} €")
                else:
                    st.info("Position aktuell genau bei Break-even.")
            else:
                st.info(f"Für {ticker} ist aktuell keine offene Paper-Position vorhanden.")

            st.markdown("---")

            st.write("### Chart")
            st.caption("Kerzenchart mit Trendlinien, Preiszonen und optionalen Markern für Backtest und Paper Trading.")

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

            fig = analysis_chart_fig
            

            st.plotly_chart(
                analysis_chart_fig,
                width="stretch",
                key="analysis_chart_main_clean"
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
