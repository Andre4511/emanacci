import pandas as pd
import plotly.graph_objects as go
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
    st.markdown("## Emanacci")
    st.caption("control panel · analyse · trading · optimisation")

    st.markdown("---")
    st.write("### Hilfe")

    if st.button("ℹ️ Einführung anzeigen"):
        st.session_state.show_onboarding = True
        st.rerun()

    # ---------------- SYMBOL ----------------
    with st.expander("📌 Symbol", expanded=True):
        st.caption(f"Aktives Symbol: {st.session_state.ticker}")
        st.caption("Wähle ein Symbol aus deiner Watchlist oder suche gezielt nach einem neuen.")

        symbol_mode = st.radio(
            "Auswahl",
            ["Watchlist", "Suche"],
            horizontal=True,
            key="symbol_mode"
        )

        if symbol_mode == "Watchlist":
            if st.session_state.watchlist:
                selected_watch_symbol = st.selectbox(
                    "Symbol aus Watchlist",
                    st.session_state.watchlist,
                    key="selected_watch_symbol"
                )

                watch_col1, watch_col2, watch_col3 = st.columns([2, 1, 1])

                with watch_col1:
                    if st.button("✅ Übernehmen", key="use_watchlist_symbol"):
                        st.session_state.ticker = selected_watch_symbol
                        st.rerun()

                with watch_col2:
                    if st.button("🗑", key="remove_watch_symbol"):
                        if selected_watch_symbol in st.session_state.watchlist:
                            st.session_state.watchlist.remove(selected_watch_symbol)
                            save_watchlist(st.session_state.watchlist)

                            if st.session_state.ticker == selected_watch_symbol:
                                if st.session_state.watchlist:
                                    st.session_state.ticker = st.session_state.watchlist[0]
                                else:
                                    st.session_state.ticker = "TSLA"

                            st.success(f"{selected_watch_symbol} entfernt.")
                            st.rerun()

                with watch_col3:
                    if st.button("🔄", key="refresh_watch_symbol"):
                        st.rerun()

                st.caption("⭐ " + " · ".join(st.session_state.watchlist[:10]))
            else:
                st.info("Deine Watchlist ist aktuell leer.")

        else:
            search_symbol = st.text_input(
                "Symbol suchen",
                value=st.session_state.ticker,
                key="ticker",
                help="Zum Beispiel: TSLA, AAPL, NVDA, BTC-USD"
            ).upper()

            search_col1, search_col2 = st.columns([2, 1])

            with search_col1:
                if st.button("🔍 Übernehmen", key="apply_search_symbol"):
                    st.session_state.ticker = search_symbol
                    st.rerun()

            with search_col2:
                if st.button("⭐ Hinzufügen", key="add_search_to_watchlist"):
                    new_symbol = search_symbol.strip().upper()
                    if new_symbol:
                        if new_symbol not in st.session_state.watchlist:
                            st.session_state.watchlist.append(new_symbol)
                            save_watchlist(st.session_state.watchlist)
                            st.success(f"{new_symbol} zur Watchlist hinzugefügt.")
                            st.rerun()
                        else:
                            st.info(f"{new_symbol} ist schon in der Watchlist.")

        compare_input = st.text_input(
            "Vergleichssymbole",
            key="compare_input",
            help="Mehrere Symbole mit Komma trennen, z. B. TSLA, AAPL, NVDA"
        )

        if st.session_state.watchlist:
            st.caption("⭐ Watchlist: " + " · ".join(st.session_state.watchlist[:8]))

    # ---------------- CHART ----------------
    with st.expander("📊 Chart", expanded=False):
        period = st.selectbox(
            "Zeitraum",
            ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y"],
            index=["1d","5d","1mo","3mo","6mo","1y","2y"].index(st.session_state.period),
            help="Wie viele historische Daten geladen werden"
        )

        interval_options = ["15m", "1h", "1d"]
        interval = st.selectbox(
            "Intervall",
            ["1m", "5m", "15m", "1h", "1d"],
            index=["1m","5m","15m","1h","1d"].index(st.session_state.interval),
            help="Zeitabstand zwischen den Kerzen"
        )

        chart_theme = st.selectbox(
            "Chart Theme",
            ["Dark", "Light"],
            index=0 if st.session_state.chart_theme == "Dark" else 1,
            key="chart_theme_select"
        )
        st.session_state.chart_theme = chart_theme

        show_trade_markers = st.checkbox(
            "Trade Marker anzeigen",
            value=st.session_state.show_trade_markers,
            help="Zeigt Käufe/Verkäufe im Chart"
        )

        show_ema = st.checkbox(
            "EMA anzeigen",
            value=st.session_state.show_ema,
            help="Trendlinien im Chart"
        )

        show_fibonacci = st.checkbox(
            "Fibonacci anzeigen",
            value=st.session_state.show_fibonacci,
            help="Unterstützung/Widerstand basierend auf Fibonacci"
        )

        show_support_resistance = st.checkbox("Support / Resistance anzeigen", key="show_support_resistance")

        show_volume = st.checkbox(
            "Volumen anzeigen",
            value=st.session_state.show_volume,
            help="Gehandeltes Volumen pro Kerze"
        )

        show_sl_tp_orders = st.checkbox("SL / TP Orders anzeigen", value=True, key="show_sl_tp_orders")

        show_paper_markers = st.checkbox("Paper-Trades im Chart anzeigen", value=True, key="show_paper_markers")

    # ---------------- STRATEGIE ----------------
    with st.expander("🤖 Strategie", expanded=False):
        fee_percent = st.number_input(
            "Gebühr (%)",
            min_value=0.0,
            max_value=5.0,
            value=st.session_state.fee_percent,
            step=0.05,
            help="Gebühr pro Kauf UND Verkauf (z.B. 0.1% pro Trade-Seite)"
        )

        stop_loss_percent = st.number_input(
            "Stop-Loss (%)",
            min_value=0.0,
            max_value=50.0,
            value=st.session_state.stop_loss_percent,
            step=0.5,
            help="Verkauft automatisch bei Verlust in %"
        )

        take_profit_percent = st.number_input(
            "Take-Profit (%)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.take_profit_percent,
            step=0.5,
            help="Verkauft automatisch bei Gewinn in %"
        )

        st.markdown("---")
        st.write("**RSI Filter**")

        use_rsi_filter = st.checkbox(
            "RSI Filter",
            value=st.session_state.use_rsi_filter,
            help="Filtert Trades basierend auf RSI (überkauft/überverkauft)"
        )

        rsi_min = st.number_input(
            "RSI Minimum",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.rsi_min,
            help="Untergrenze für Einstieg"
        )

        rsi_max = st.number_input(
            "RSI Maximum",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.rsi_max,
            help="Obergrenze für Einstieg"
        )

        st.markdown("---")
        st.write("**Trendfilter**")

        use_ema200_filter = st.checkbox(
            "EMA200 Filter",
            value=st.session_state.use_ema200_filter,
            help="Handelt nur in Trendrichtung (über EMA200)"
        )

    # ---------------- OPTIMIERUNG ----------------
    with st.expander("🧪 Optimierung", expanded=False):
        optimization_target = st.selectbox(
            "Optimieren nach",
            ["Return %", "Profit Factor", "Win Rate %", "Max Drawdown %", "Optimierungs-Score"],
            index=0,
            key="optimization_target"
        )

        heatmap_metric = st.selectbox(
            "Heatmap anzeigen für",
            ["Return %", "Profit Factor", "Win Rate %", "Max Drawdown %", "Optimierungs-Score"],
            index=0,
            key="heatmap_metric"
        )

        st.write("**Score-Gewichte**")

        score_weight_return = st.number_input(
            "Gewicht Return",
            min_value=0.0,
            max_value=50.0,
            step=0.5,
            key="score_weight_return"
        )

        score_weight_pf = st.number_input(
            "Gewicht Profit Factor",
            min_value=0.0,
            max_value=50.0,
            step=0.5,
            key="score_weight_pf"
        )

        score_weight_winrate = st.number_input(
            "Gewicht Win Rate",
            min_value=0.0,
            max_value=10.0,
            step=0.1,
            key="score_weight_winrate"
        )

        score_weight_drawdown = st.number_input(
            "Gewicht Drawdown",
            min_value=0.0,
            max_value=50.0,
            step=0.5,
            key="score_weight_drawdown"
        )

        st.markdown("---")
        st.write("**Optimierungs-Bereiche**")

        optimization_sl_input = st.text_input(
            "Stop-Loss Werte",
            value=st.session_state.optimization_sl_input,
            help="Mehrere Werte mit Komma trennen, z.B. 3,5,7"
        )

        optimization_tp_input = st.text_input(
            "Take-Profit Werte (%)",
            key="optimization_tp_input"
        )

        optimization_rsi_input = st.text_input(
            "RSI Bereiche",
            value=st.session_state.optimization_rsi_input,
            help="Format: 40-70, 45-65"
        )

    # ---------------- PRESETS ----------------
    with st.expander("🎯 Presets", expanded=False):
        selected_preset = st.selectbox(
            "Preset wählen",
            ["Keins"] + list(PRESETS.keys()),
            key="selected_preset"
        )

        apply_preset = st.button("🎯 Preset anwenden")

        if apply_preset and selected_preset != "Keins":
            preset = PRESETS[selected_preset]

            st.session_state.period = preset["period"]
            st.session_state.interval = preset["interval"]
            st.session_state.fee_percent = preset["fee_percent"]
            st.session_state.stop_loss_percent = preset["stop_loss_percent"]
            st.session_state.take_profit_percent = preset["take_profit_percent"]
            st.session_state.use_rsi_filter = preset["use_rsi_filter"]
            st.session_state.rsi_min = preset["rsi_min"]
            st.session_state.rsi_max = preset["rsi_max"]
            st.session_state.use_ema200_filter = preset["use_ema200_filter"]
            st.session_state.show_trade_markers = preset["show_trade_markers"]
            st.session_state.show_ema = preset["show_ema"]
            st.session_state.show_fibonacci = preset["show_fibonacci"]
            st.session_state.show_support_resistance = preset["show_support_resistance"]
            st.session_state.show_volume = preset["show_volume"]
            st.session_state.chart_theme = preset["chart_theme"]
            st.rerun()

    st.markdown("---")

    # ---------------- PAPER TRADING ----------------
    with st.expander("💼 Paper Trading", expanded=False):

        st.write(f"**Spielgeld:** {st.session_state.paper_cash:,.2f} €")

        # Handelsmodus
        paper_trade_mode = st.radio(
            "Handelsmodus",
            ["Stückzahl", "Betrag (€)"],
            key="paper_trade_mode"
        )

        # Eingabe je nach Modus
        if paper_trade_mode == "Stückzahl":
            st.number_input(
                "Stückzahl",
                min_value=1,
                value=1,
                step=1,
                key="paper_trade_quantity",
                help="Wie viele Aktien kaufen/verkaufen"
            )
        else:
            st.number_input(
                "Betrag (€)",
                min_value=1.0,
                value=1000.0,
                step=50.0,
                key="paper_trade_amount",
                help="Wie viel Geld investieren"
            )

        buy_paper = st.button("🟢 Virtuell kaufen")
        sell_paper = st.button("🔴 Virtuell verkaufen")

        # ---------------- BUY ----------------
        if buy_paper:
            paper_data = load_data(ticker, period="5d", interval="1d")

            if not paper_data.empty and "Close" in paper_data.columns:
                current_price = float(paper_data["Close"].iloc[-1])
                trade_time = paper_data.index[-1]
                fee_rate = st.session_state.fee_percent / 100

                # Stückzahl-Modus
                if paper_trade_mode == "Stückzahl":
                    quantity = int(st.session_state.paper_trade_quantity)
                    gross_cost = current_price * quantity
                    fee_cost = gross_cost * fee_rate
                    total_cost = gross_cost + fee_cost

                # Betrag-Modus
                else:
                    invest_amount = float(st.session_state.paper_trade_amount)

                    if invest_amount > st.session_state.paper_cash:
                        st.error("Nicht genug Spielgeld verfügbar.")
                        st.stop()

                    fee_cost = invest_amount * fee_rate
                    net_invest_amount = invest_amount - fee_cost
                    quantity = int(net_invest_amount / current_price)

                    if quantity < 1:
                        st.error("Betrag ist zu klein für mindestens 1 Stück.")
                        st.stop()

                    gross_cost = current_price * quantity
                    fee_cost = gross_cost * fee_rate
                    total_cost = gross_cost + fee_cost

                # Kauf durchführen
                if st.session_state.paper_cash >= total_cost:
                    st.session_state.paper_cash -= total_cost

                    if ticker not in st.session_state.paper_positions:
                        st.session_state.paper_positions[ticker] = {
                            "quantity": 0,
                            "avg_price": 0.0,
                            "total_cost": 0.0
                        }

                    old_qty = st.session_state.paper_positions[ticker]["quantity"]
                    old_total_cost = st.session_state.paper_positions[ticker]["total_cost"]

                    new_qty = old_qty + quantity
                    new_total_cost = old_total_cost + total_cost
                    new_avg = new_total_cost / new_qty

                    st.session_state.paper_positions[ticker]["quantity"] = new_qty
                    st.session_state.paper_positions[ticker]["avg_price"] = new_avg
                    st.session_state.paper_positions[ticker]["total_cost"] = new_total_cost

                    st.session_state.paper_history.append({
                        "Zeit": trade_time,
                        "Typ": "Kauf",
                        "Symbol": ticker,
                        "Stück": quantity,
                        "Preis": round(current_price, 2),
                        "Gebühr": round(fee_cost, 2),
                        "Gesamt": round(total_cost, 2)
                    })

                    update_paper_equity_snapshot()
                    st.success(f"{quantity} Stück {ticker} gekauft.")
                    st.rerun()
                else:
                    st.error("Nicht genug Spielgeld verfügbar.")
            else:
                st.error("Kein Preis verfügbar.")

        # ---------------- SELL ----------------
        if sell_paper:
            paper_data = load_data(ticker, period="5d", interval="1d")

            if not paper_data.empty and "Close" in paper_data.columns:
                current_price = float(paper_data["Close"].iloc[-1])
                trade_time = paper_data.index[-1]
                fee_rate = st.session_state.fee_percent / 100

                if ticker in st.session_state.paper_positions:
                    position = st.session_state.paper_positions[ticker]
                    held_qty = position["quantity"]

                    # Stückzahl-Modus
                    if paper_trade_mode == "Stückzahl":
                        quantity = int(st.session_state.paper_trade_quantity)

                    # Betrag-Modus
                    else:
                        sell_amount = float(st.session_state.paper_trade_amount)
                        quantity = int(sell_amount / current_price)

                        if quantity < 1:
                            st.error("Betrag zu klein.")
                            st.stop()

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
                            st.session_state.paper_positions[ticker]["quantity"] = remaining_qty
                            st.session_state.paper_positions[ticker]["total_cost"] = remaining_total_cost
                            st.session_state.paper_positions[ticker]["avg_price"] = remaining_total_cost / remaining_qty
                        else:
                            del st.session_state.paper_positions[ticker]

                        st.session_state.paper_history.append({
                            "Zeit": trade_time,
                            "Typ": "Verkauf",
                            "Symbol": ticker,
                            "Stück": quantity,
                            "Preis": round(current_price, 2),
                            "Gebühr": round(fee_cost, 2),
                            "Gesamt": round(total_value, 2),
                            "Realized PnL": round(realized_pnl, 2)
                        })

                        update_paper_equity_snapshot()
                        st.success(f"{quantity} Stück {ticker} verkauft.")
                        st.rerun()
                    else:
                        st.error("Nicht genug Stück vorhanden.")
                else:
                    st.error("Keine Position vorhanden.")
            else:
                st.error("Kein Preis verfügbar.")

        st.write("### 📊 Depot Übersicht")

        total_positions_value = 0
        position_rows = []

        paper_data = load_data(ticker, period="5d", interval="1d")

        current_price = None
        if not paper_data.empty and "Close" in paper_data.columns:
            current_price = float(paper_data["Close"].iloc[-1])

        for symbol, pos in st.session_state.paper_positions.items():

            quantity = pos["quantity"]
            avg_price = pos["avg_price"]
            total_cost = pos.get("total_cost", quantity * avg_price)

            symbol_data = load_data(symbol, period="5d", interval="1d")

            if symbol_data.empty or "Close" not in symbol_data.columns:
                continue

            current_price_symbol = float(symbol_data["Close"].iloc[-1])

            market_value = quantity * current_price_symbol
            open_pnl = market_value - total_cost
            open_pnl_pct = (open_pnl / total_cost * 100) if total_cost > 0 else 0

            total_positions_value += market_value

            position_rows.append({
                "Symbol": symbol,
                "Stück": quantity,
                "Ø Kaufpreis": round(avg_price, 2),
                "Aktueller Preis": round(current_price_symbol, 2),
                "Einstand": round(total_cost, 2),
                "Marktwert": round(market_value, 2),
                "PnL (€)": round(open_pnl, 2),
                "PnL (%)": round(open_pnl_pct, 2)
            })

        cash = st.session_state.paper_cash
        total_portfolio_value = cash + total_positions_value
        total_pnl = total_portfolio_value - 10000  # Startkapital
        total_pnl_pct = (total_pnl / 10000 * 100)

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("💰 Cash", f"{cash:,.2f} €")
        c2.metric("📦 Positionswert", f"{total_positions_value:,.2f} €")
        c3.metric("🏦 Gesamtwert", f"{total_portfolio_value:,.2f} €")
        c4.metric("📈 Gesamt-PnL", f"{total_pnl:,.2f} €", f"{total_pnl_pct:.2f}%")

        st.caption(f"Aktives Symbol für Paper Trading: {ticker}")

        if position_rows:
            df_positions = pd.DataFrame(position_rows)

            st.dataframe(df_positions, width="stretch")
        else:
            st.info("Keine offenen Positionen")

    if st.button("💾 Einstellungen speichern"):
        settings_to_save = {
            "ticker": st.session_state.ticker,
            "symbol_mode": st.session_state.symbol_mode,
            "compare_input": st.session_state.compare_input,
            "period": st.session_state.period,
            "interval": st.session_state.interval,
            "fee_percent": st.session_state.fee_percent,
            "stop_loss_percent": st.session_state.stop_loss_percent,
            "take_profit_percent": st.session_state.take_profit_percent,
            "use_rsi_filter": st.session_state.use_rsi_filter,
            "rsi_min": st.session_state.rsi_min,
            "rsi_max": st.session_state.rsi_max,
            "use_ema200_filter": st.session_state.use_ema200_filter,
            "show_trade_markers": st.session_state.show_trade_markers,
            "show_ema": st.session_state.show_ema,
            "show_fibonacci": st.session_state.show_fibonacci,
            "show_support_resistance": st.session_state.show_support_resistance,
            "show_volume": st.session_state.show_volume,
            "chart_theme": st.session_state.chart_theme,
            "optimization_sl_input": st.session_state.optimization_sl_input,
            "optimization_tp_input": st.session_state.optimization_tp_input,
            "optimization_rsi_input": st.session_state.optimization_rsi_input,
            "score_weight_return": st.session_state.score_weight_return,
            "score_weight_pf": st.session_state.score_weight_pf,
            "score_weight_winrate": st.session_state.score_weight_winrate,
            "score_weight_drawdown": st.session_state.score_weight_drawdown,
            "paper_benchmark": st.session_state.paper_benchmark,
            "paper_benchmark_mode": st.session_state.paper_benchmark_mode,
            "paper_benchmark_custom": st.session_state.paper_benchmark_custom,
            "show_onboarding": st.session_state.show_onboarding,
            "show_sl_tp_orders": st.session_state.show_sl_tp_orders,
        }
        save_user_settings(settings_to_save)
        st.success("Einstellungen wurden gespeichert.")

    if st.button("Einstellungen zurücksetzen"):
        st.session_state.ticker = "TSLA"
        st.session_state.symbol_mode = "Watchlist"
        st.session_state.compare_input = "TSLA, AAPL, NVDA"
        st.session_state.period = "3mo"
        st.session_state.interval = "1d"
        st.session_state.fee_percent = 0.1
        st.session_state.stop_loss_percent = 5.0
        st.session_state.take_profit_percent = 10.0
        st.session_state.use_rsi_filter = True
        st.session_state.rsi_min = 40.0
        st.session_state.rsi_max = 70.0
        st.session_state.use_ema200_filter = False
        st.session_state.chart_theme = "Dark"
        st.session_state.show_trade_markers = True
        st.session_state.show_ema = True
        st.session_state.show_fibonacci = True
        st.session_state.show_support_resistance = True
        st.session_state.show_volume = True
        st.session_state.optimization_sl_input = "3,5,7"
        st.session_state.optimization_tp_input = "6,10,15"
        st.session_state.optimization_rsi_input = "35-75,40-70,45-65"
        st.session_state.score_weight_return = 1.0
        st.session_state.score_weight_pf = 10.0
        st.session_state.score_weight_winrate = 0.2
        st.session_state.score_weight_drawdown = 1.0
        st.session_state.paper_benchmark = "SPY"
        st.session_state.paper_benchmark_mode = "SPY"
        st.session_state.paper_benchmark_custom = "SPY"
        st.session_state.show_onboarding = True
        st.session_state.show_sl_tp_orders = True
        save_user_settings({
            "ticker": "TSLA",
            "symbol_mode": "Watchlist",
            "compare_input": "TSLA, AAPL, NVDA",
            "period": "3mo",
            "interval": "1d",
            "fee_percent": 0.1,
            "stop_loss_percent": 5.0,
            "take_profit_percent": 10.0,
            "use_rsi_filter": True,
            "rsi_min": 40.0,
            "rsi_max": 70.0,
            "use_ema200_filter": False,
            "show_trade_markers": True,
            "show_ema": True,
            "show_fibonacci": True,
            "show_support_resistance": True,
            "show_volume": True,
            "chart_theme": "Dark",
            "optimization_sl_input": "3,5,7",
            "optimization_tp_input": "6,10,15",
            "optimization_rsi_input": "35-75,40-70,45-65",
            "score_weight_return": 1.0,
            "score_weight_pf": 10.0,
            "score_weight_winrate": 0.2,
            "score_weight_drawdown": 1.0,
            "paper_benchmark": "SPY",
            "paper_benchmark_mode": "SPY",
            "paper_benchmark_custom": "SPY",
            "show_onboarding": True,
            "show_sl_tp_orders": True,
        })
        st.rerun()

    st.write("### 🤖 Auto SL/TP")

    auto_sl_tp = st.checkbox(
        "Automatisch SL/TP setzen",
        value=True,
        key="auto_sl_tp"
    )

    auto_sl_percent = st.number_input(
        "Stop-Loss (%)",
        min_value=0.1,
        max_value=50.0,
        value=5.0,
        step=0.5,
        key="auto_sl_percent"
    )

    auto_tp_percent = st.number_input(
        "Take-Profit (%)",
        min_value=0.1,
        max_value=100.0,
        value=10.0,
        step=0.5,
        key="auto_tp_percent"
    )

    use_trailing_stop = st.checkbox(
        "Trailing Stop",
        value=st.session_state.use_trailing_stop,
        help="Stop-Loss bewegt sich automatisch mit dem Kurs"
    )

    trailing_stop_percent = st.number_input(
        "Trailing Stop (%)",
        min_value=0.1,
        max_value=50.0,
        value=st.session_state.trailing_stop_percent,
        step=0.5,
        help="Abstand zum aktuellen Hoch in %"
    )

tab_analyse, tab_vergleich, tab_watchlist, tab_paper = st.tabs(
    ["📈 Einzelanalyse", "📊 Vergleich", "⭐ Watchlist", "💼 Paper Trading"]
)

with tab_watchlist:
    st.write("### ⭐ Watchlist")

    new_watch_symbol = st.text_input(
        "Symbol zur Watchlist hinzufügen",
        "",
        key="watch_add"
    ).upper()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Zur Watchlist hinzufügen", key="btn_add_watch"):
            if new_watch_symbol:
                if new_watch_symbol not in st.session_state.watchlist:
                    st.session_state.watchlist.append(new_watch_symbol)
                    save_watchlist(st.session_state.watchlist)
                    st.success(f"{new_watch_symbol} wurde zur Watchlist hinzugefügt.")
                else:
                    st.info(f"{new_watch_symbol} ist schon in der Watchlist.")
            else:
                st.warning("Bitte ein Symbol eingeben.")

    with col2:
        remove_symbol = st.selectbox(
            "Symbol aus Watchlist entfernen",
            [""] + st.session_state.watchlist,
            key="watch_remove"
        )
        if st.button("Aus Watchlist entfernen", key="btn_remove_watch"):
            if remove_symbol and remove_symbol in st.session_state.watchlist:
                st.session_state.watchlist.remove(remove_symbol)
                save_watchlist(st.session_state.watchlist)
                st.success(f"{remove_symbol} wurde aus der Watchlist entfernt.")
            else:
                st.warning("Bitte ein gültiges Symbol auswählen.")

    if st.session_state.watchlist:
        st.write("Aktuelle Watchlist:")
        st.write(", ".join(st.session_state.watchlist))
    else:
        st.info("Die Watchlist ist aktuell leer.")

with tab_paper:
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

    if position_rows:
        sorted_positions = sorted(position_rows, key=lambda x: x["Offener PnL"], reverse=True)

        for i in range(0, len(sorted_positions), 2):
            grid_col1, grid_col2 = st.columns(2)

            # Linke Karte
            pos_left = sorted_positions[i]
            pnl_value_left = float(pos_left["Offener PnL"])

            if pnl_value_left > 0:
                pnl_class_left = "em-card-positive"
                pnl_label_left = "Gewinn"
            elif pnl_value_left < 0:
                pnl_class_left = "em-card-negative"
                pnl_label_left = "Verlust"
            else:
                pnl_class_left = "em-card-neutral"
                pnl_label_left = "Break-even"

            with grid_col1:
                st.markdown(
                    f"""
                    <div class="em-card {pnl_class_left}">
                        <div class="em-card-title">{pos_left["Symbol"]}</div>
                        <div class="em-card-sub">Stück: {pos_left["Stück"]}</div>
                        <div class="em-card-sub">Ø Kaufpreis: {pos_left["Ø Kaufpreis"]:.2f} €</div>
                        <div class="em-card-sub">Aktueller Preis: {pos_left["Aktueller Preis"]:.2f} €</div>
                        <div class="em-card-sub">Einstand gesamt: {pos_left["Einstand gesamt"]:.2f} €</div>
                        <div class="em-card-sub">Marktwert: {pos_left["Marktwert"]:.2f} €</div>
                        <div class="em-card-sub"><strong>{pnl_label_left}: {pos_left["Offener PnL"]:.2f} € ({pos_left["Offener PnL %"]:.2f}%)</strong></div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # Rechte Karte nur wenn vorhanden
            if i + 1 < len(sorted_positions):
                pos_right = sorted_positions[i + 1]
                pnl_value_right = float(pos_right["Offener PnL"])

                if pnl_value_right > 0:
                    pnl_class_right = "em-card-positive"
                    pnl_label_right = "Gewinn"
                elif pnl_value_right < 0:
                    pnl_class_right = "em-card-negative"
                    pnl_label_right = "Verlust"
                else:
                    pnl_class_right = "em-card-neutral"
                    pnl_label_right = "Break-even"

                with grid_col2:
                    st.markdown(
                        f"""
                        <div class="em-card {pnl_class_right}">
                            <div class="em-card-title">{pos_right["Symbol"]}</div>
                            <div class="em-card-sub">Stück: {pos_right["Stück"]}</div>
                            <div class="em-card-sub">Ø Kaufpreis: {pos_right["Ø Kaufpreis"]:.2f} €</div>
                            <div class="em-card-sub">Aktueller Preis: {pos_right["Aktueller Preis"]:.2f} €</div>
                            <div class="em-card-sub">Einstand gesamt: {pos_right["Einstand gesamt"]:.2f} €</div>
                            <div class="em-card-sub">Marktwert: {pos_right["Marktwert"]:.2f} €</div>
                            <div class="em-card-sub"><strong>{pnl_label_right}: {pos_right["Offener PnL"]:.2f} € ({pos_right["Offener PnL %"]:.2f}%)</strong></div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        with st.expander("📋 Tabellenansicht offene Positionen", expanded=False):
            positions_df = pd.DataFrame(sorted_positions)
            st.dataframe(positions_df, width="stretch")
    else:
        st.info("Noch keine offenen Positionen.")

    # ---------------- EQUITY CURVE ----------------
    st.write("### Equity Curve")

    if st.session_state.paper_equity_history:
        equity_curve_df = pd.DataFrame(st.session_state.paper_equity_history)
        equity_curve_df["Zeit"] = pd.to_datetime(equity_curve_df["Zeit"], errors="coerce")

        equity_fig = go.Figure()

        equity_fig.add_trace(
            go.Scatter(
                x=equity_curve_df["Zeit"],
                y=equity_curve_df["Gesamtwert"],
                mode="lines+markers",
                name="Paper Equity"
            )
        )

        equity_fig.update_layout(
            height=400,
            xaxis_title="Zeit",
            yaxis_title="Depotwert (€)",
            hovermode="x unified"
        )

        st.plotly_chart(equity_fig, width="stretch")
    else:
        st.info("Noch keine Equity-Daten vorhanden. Führe zuerst virtuelle Trades aus.")

    st.markdown("---")

    # ---------------- BENCHMARK ----------------
    st.write("### 🆚 Benchmark-Vergleich")

    benchmark_options = ["SPY", "QQQ", "BTC-USD", "^GDAXI"]

    if ticker not in benchmark_options:
        benchmark_options.append(ticker)

    benchmark_options.append("Custom")

    benchmark_mode = st.selectbox(
        "Benchmark wählen",
        benchmark_options,
        key="paper_benchmark_mode"
    )

    if benchmark_mode == "Custom":
        benchmark_symbol = st.text_input(
            "Custom Benchmark Symbol",
            key="paper_benchmark_custom"
        ).upper()
    else:
        benchmark_symbol = benchmark_mode

    if st.session_state.paper_equity_history:
        equity_curve_df = pd.DataFrame(st.session_state.paper_equity_history)
        equity_curve_df["Zeit"] = pd.to_datetime(equity_curve_df["Zeit"], errors="coerce")

        if not equity_curve_df.empty:
            start_time = equity_curve_df["Zeit"].iloc[0]

            try:
                bh_data = load_data(benchmark_symbol, period="1y", interval="1d")

                if not bh_data.empty and "Close" in bh_data.columns:
                    bh_data = bh_data.copy()
                    bh_data.index = pd.to_datetime(bh_data.index, errors="coerce")
                    bh_data = bh_data[bh_data.index >= start_time]

                    if not bh_data.empty:
                        start_price = float(bh_data["Close"].iloc[0])

                        bh_data["BuyHold"] = (
                            bh_data["Close"] / start_price
                        ) * st.session_state.paper_start_cash

                        compare_paper_fig = go.Figure()

                        compare_paper_fig.add_trace(
                            go.Scatter(
                                x=equity_curve_df["Zeit"],
                                y=equity_curve_df["Gesamtwert"],
                                mode="lines+markers",
                                name="Paper Trading"
                            )
                        )

                        compare_paper_fig.add_trace(
                            go.Scatter(
                                x=bh_data.index,
                                y=bh_data["BuyHold"],
                                mode="lines",
                                name=f"Buy & Hold ({benchmark_symbol})"
                            )
                        )

                        compare_paper_fig.update_layout(
                            height=420,
                            xaxis_title="Zeit",
                            yaxis_title="Wert (€)",
                            hovermode="x unified"
                        )

                        st.plotly_chart(compare_paper_fig, width="stretch")

                        paper_final = float(equity_curve_df["Gesamtwert"].iloc[-1])
                        buyhold_final = float(bh_data["BuyHold"].iloc[-1])

                        paper_return = ((paper_final / st.session_state.paper_start_cash) - 1) * 100
                        buyhold_return = ((buyhold_final / st.session_state.paper_start_cash) - 1) * 100

                        b1, b2 = st.columns(2)
                        b1.metric("Paper Trading Return", f"{paper_return:.2f}%")
                        b2.metric(f"Buy & Hold Return ({benchmark_symbol})", f"{buyhold_return:.2f}%")

                        if paper_return > buyhold_return:
                            st.success(f"Dein Paper Trading liegt aktuell vor Buy & Hold ({benchmark_symbol}).")
                        elif paper_return < buyhold_return:
                            st.warning(f"Buy & Hold ({benchmark_symbol}) liegt aktuell vor deinem Paper Trading.")
                        else:
                            st.info("Beide liegen aktuell gleichauf.")
                    else:
                        st.info("Nicht genug Buy-&-Hold-Daten ab dem Startzeitpunkt verfügbar.")
                else:
                    st.info(f"Keine Buy-&-Hold-Daten für {benchmark_symbol} verfügbar.")
            except Exception as e:
                st.warning(f"Buy-&-Hold-Vergleich aktuell nicht möglich: {e}")
    else:
        st.info("Noch keine Equity-Daten für den Vergleich vorhanden.")

    st.write("### Offene Orders (Limit / SL / TP)")

    if st.session_state.paper_open_orders:
        st.caption("Alle offenen Limit-, Stop-Loss-, Take-Profit- und Trailing-Orders.")

        orders_list = st.session_state.paper_open_orders

        for i in range(0, len(orders_list), 2):
            order_col1, order_col2 = st.columns(2)

            # Linke Order
            order_left = orders_list[i]
            order_type_left = order_left.get("Order Type", "Order")
            symbol_left = order_left.get("Symbol", "-")
            quantity_left = order_left.get("Stück", 0)
            limit_price_left = float(order_left.get("Limit Price", 0.0))

            if order_type_left == "Limit Buy":
                badge_class_left = "em-badge-buy"
            elif order_type_left == "Limit Sell":
                badge_class_left = "em-badge-sell"
            elif order_type_left == "Stop-Loss":
                badge_class_left = "em-badge-sl"
            elif order_type_left == "Take-Profit":
                badge_class_left = "em-badge-tp"
            elif order_type_left == "Trailing Stop":
                badge_class_left = "em-badge-ts"
            else:
                badge_class_left = "em-badge-buy"

            anchor_text_left = ""
            if "Anchor Price" in order_left:
                anchor_text_left = f"<div class='em-card-sub'>Anchor: {float(order_left['Anchor Price']):.2f} €</div>"

            with order_col1:
                st.markdown(
                    f"""
                    <div class="em-card">
                        <div class="em-badge {badge_class_left}">{order_type_left}</div>
                        <div class="em-card-title">{symbol_left}</div>
                        <div class="em-card-sub">Stück: {quantity_left}</div>
                        <div class="em-card-sub">Preis: {limit_price_left:.2f} €</div>
                        {anchor_text_left}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if st.button("❌ Order löschen", key=f"cancel_order_left_{i}"):
                    st.session_state.paper_open_orders.pop(i)
                    st.success("Order gelöscht.")
                    st.rerun()

            # Rechte Order nur wenn vorhanden
            if i + 1 < len(orders_list):
                order_right = orders_list[i + 1]
                order_type_right = order_right.get("Order Type", "Order")
                symbol_right = order_right.get("Symbol", "-")
                quantity_right = order_right.get("Stück", 0)
                limit_price_right = float(order_right.get("Limit Price", 0.0))

                anchor_text_right = ""
                if "Anchor Price" in order_right:
                    anchor_text_right = f"<div class='em-card-sub'>Anchor: {float(order_right['Anchor Price']):.2f} €</div>"

                
                def get_badge_class(order_type):
                    if order_type == "Limit Buy":
                        return "em-badge-buy"
                    elif order_type == "Limit Sell":
                        return "em-badge-sell"
                    elif order_type == "Stop-Loss":
                        return "em-badge-sl"
                    elif order_type == "Take-Profit":
                        return "em-badge-tp"
                    elif order_type == "Trailing Stop":
                        return "em-badge-ts"
                    return "em-badge-buy"

                badge_class_right = get_badge_class(order_type_right)
                
                with order_col2:
                    st.markdown(
                        f"""
                        <div class="em-card">
                            <div class="em-badge {badge_class_right}">{order_type_right}</div>
                            <div class="em-card-title">{symbol_right}</div>
                            <div class="em-card-sub">Stück: {quantity_right}</div>
                            <div class="em-card-sub">Preis: {limit_price_right:.2f} €</div>
                            {anchor_text_right}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    if st.button("❌ Order löschen", key=f"cancel_order_right_{i+1}"):
                        st.session_state.paper_open_orders.pop(i + 1)
                        st.success("Order gelöscht.")
                        st.rerun()

        if st.button("🗑 Alle Orders löschen", key="cancel_all_orders"):
            st.session_state.paper_open_orders = []
            st.success("Alle offenen Orders wurden gelöscht.")
            st.rerun()

        with st.expander("📋 Tabellenansicht offene Orders", expanded=False):
            open_orders_df = pd.DataFrame(st.session_state.paper_open_orders)
            st.dataframe(open_orders_df, width="stretch")

    st.markdown("---")

    # ---------------- HISTORIE ----------------
    st.write("### Trade-Historie")

    if history:
        history_df = pd.DataFrame(history)
        st.dataframe(history_df, width="stretch")
    else:
        st.info("Noch keine virtuellen Trades.")

    st.markdown("---")

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
            st.markdown("""
            <div class="em-section">
                <div class="em-kicker">Analysebereich</div>
                <div><strong>Chart, Position, Trading, Indikatoren und Backtesting</strong></div>
                <div style="opacity:0.8; margin-top:0.25rem;">
                    Hier analysierst du das aktuelle Symbol, handelst virtuell und prüfst Strategie, Signale und Risiko.
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("ℹ️ Begriffe kurz erklärt", expanded=False):
                st.write("""
                **EMA** zeigt den gleitenden Durchschnitt des Kurses und hilft dabei, den Trend besser zu erkennen.  
                **RSI** misst, ob ein Markt eher überkauft oder überverkauft ist, also ob der Kurs vielleicht schon zu stark gestiegen oder gefallen ist.  
                **MACD** ist ein Trend- und Momentum-Indikator, der oft Hinweise auf mögliche Richtungswechsel gibt.  
                **Fibonacci** zeigt mögliche Preiszonen, an denen der Kurs reagieren, stoppen oder wieder drehen könnte.  
                **Stop-Loss**, **Take-Profit** und **Trailing Stop** helfen dir dabei, Verluste zu begrenzen, Gewinne mitzunehmen und Positionen automatischer zu verwalten.
                """)

            st.write("### Letzte Kursdaten")
            st.caption("Die letzten geladenen Marktdaten für das ausgewählte Symbol.")
            st.dataframe(data.tail())

            if chart_theme == "Dark":
                chart_template = "plotly_dark"
                chart_bg = "#08101f"
                paper_bg = "#050914"
                font_color = "#dfe7ff"
                grid_color = "rgba(120, 180, 255, 0.08)"
                candle_up = "#26a69a"
                candle_down = "#ef5350"
                volume_color = "rgba(120, 144, 156, 0.45)"
            else:
                chart_template = "plotly_white"
                chart_bg = "rgba(245, 248, 255, 0.96)"
                paper_bg = "rgba(255, 255, 255, 0.98)"
                font_color = "#111111"
                grid_color = "rgba(0, 0, 0, 0.08)"
                candle_up = "#26a69a"
                candle_down = "#ef5350"
                volume_color = "rgba(120, 144, 156, 0.35)"

            st.write("### 🟢 Trading")

            col1, col2, col3 = st.columns(3)

            with col1:
                trade_quantity = st.number_input(
                    "Menge",
                    min_value=1,
                    value=1,
                    step=1,
                    key="chart_trade_qty"
                )

            with col2:
                buy_button = st.button("🟢 BUY", use_container_width=True)

            with col3:
                sell_button = st.button("🔴 SELL", use_container_width=True)
            
            current_price = float(data["Close"].iloc[-1])
            fee_rate = st.session_state.fee_percent / 100

            st.write("### 💼 Aktueller Positionsstatus")

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

                sell_col1, sell_col2, sell_col3 = st.columns([1, 1, 2])

                with sell_col1:
                    partial_sell_qty = st.number_input(
                        "Teilverkauf Stück",
                        min_value=1,
                        max_value=int(quantity),
                        value=1,
                        step=1,
                        key=f"partial_sell_qty_{ticker}"
                    )

                with sell_col2:
                    if st.button("🟠 Teilverkauf", key=f"partial_sell_{ticker}"):
                        fee_rate = st.session_state.fee_percent / 100

                        sell_quantity = int(partial_sell_qty)
                        gross_value = current_price * sell_quantity
                        fee_cost = gross_value * fee_rate
                        total_value = gross_value - fee_cost

                        cost_basis_sold = avg_price * sell_quantity
                        realized_pnl = total_value - cost_basis_sold

                        st.session_state.paper_cash += total_value

                        remaining_qty = quantity - sell_quantity
                        remaining_total_cost = total_cost - cost_basis_sold

                        if remaining_qty > 0:
                            st.session_state.paper_positions[ticker]["quantity"] = remaining_qty
                            st.session_state.paper_positions[ticker]["total_cost"] = remaining_total_cost
                            st.session_state.paper_positions[ticker]["avg_price"] = remaining_total_cost / remaining_qty
                        else:
                            del st.session_state.paper_positions[ticker]

                        st.session_state.paper_history.append({
                            "Zeit": datetime.now(),
                            "Typ": "Verkauf",
                            "Symbol": ticker,
                            "Stück": sell_quantity,
                            "Preis": round(current_price, 2),
                            "Gebühr": round(fee_cost, 2),
                            "Gesamt": round(total_value, 2),
                            "Realized PnL": round(realized_pnl, 2)
                        })

                        update_paper_equity_snapshot()
                        st.success(f"{sell_quantity} Stück {ticker} wurden verkauft.")
                        st.rerun()

                with sell_col3:
                    if st.button("🔴 Alles verkaufen", key=f"sell_all_{ticker}"):
                        fee_rate = st.session_state.fee_percent / 100

                        gross_value = current_price * quantity
                        fee_cost = gross_value * fee_rate
                        total_value = gross_value - fee_cost

                        realized_pnl = total_value - total_cost

                        st.session_state.paper_cash += total_value
                        del st.session_state.paper_positions[ticker]

                        st.session_state.paper_history.append({
                            "Zeit": datetime.now(),
                            "Typ": "Verkauf",
                            "Symbol": ticker,
                            "Stück": quantity,
                            "Preis": round(current_price, 2),
                            "Gebühr": round(fee_cost, 2),
                            "Gesamt": round(total_value, 2),
                            "Realized PnL": round(realized_pnl, 2)
                        })

                        update_paper_equity_snapshot()
                        st.success(f"Alle {quantity} Stück {ticker} wurden verkauft.")
                        st.rerun()

            else:
                st.info(f"Für {ticker} ist aktuell keine offene Paper-Position vorhanden.")
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

                pnl_col1, pnl_col2, pnl_col3, pnl_col4 = st.columns(4)

                pnl_col1.metric("Position", f"{quantity} Stück")
                pnl_col2.metric("Ø Kaufpreis", f"{avg_price:.2f} €")
                pnl_col3.metric("Marktwert", f"{market_value:.2f} €")
                pnl_col4.metric("PnL", f"{open_pnl:.2f} €", f"{open_pnl_pct:.2f}%")

                if open_pnl > 0:
                    st.success(f"{ticker}: Position im Gewinn ({open_pnl:.2f} €)")
                elif open_pnl < 0:
                    st.warning(f"{ticker}: Position im Verlust ({open_pnl:.2f} €)")
                else:
                    st.info(f"{ticker}: Position aktuell bei Break-even")
            else:
                st.caption(f"Für {ticker} ist aktuell keine offene Paper-Position vorhanden.")

            st.write("### Trading-Leiste")

            trade_bar_col1, trade_bar_col2, trade_bar_col3, trade_bar_col4 = st.columns([1, 1, 1, 2])

            with trade_bar_col1:
                quick_trade_qty = st.number_input(
                    "Menge",
                    min_value=1,
                    value=1,
                    step=1,
                    key=f"quick_trade_qty_{ticker}"
                )

            with trade_bar_col2:
                quick_buy = st.button("🟢 Buy", key=f"quick_buy_{ticker}")

            with trade_bar_col3:
                quick_sell = st.button("🟠 Sell", key=f"quick_sell_{ticker}")

            with trade_bar_col4:
                quick_sell_all = st.button("🔴 Alles verkaufen", key=f"quick_sell_all_bar_{ticker}")

            current_price = float(data["Close"].iloc[-1])
            fee_rate = st.session_state.fee_percent / 100

            if quick_buy:
                quantity = int(quick_trade_qty)
                gross_cost = current_price * quantity
                fee_cost = gross_cost * fee_rate
                total_cost = gross_cost + fee_cost

                if st.session_state.paper_cash >= total_cost:
                    if ticker not in st.session_state.paper_positions:
                        st.session_state.paper_positions[ticker] = {
                            "quantity": 0,
                            "avg_price": 0.0,
                            "total_cost": 0.0
                        }

                    old_qty = st.session_state.paper_positions[ticker]["quantity"]
                    old_total_cost = st.session_state.paper_positions[ticker]["total_cost"]

                    new_qty = old_qty + quantity
                    new_total_cost = old_total_cost + total_cost
                    new_avg = new_total_cost / new_qty

                    st.session_state.paper_positions[ticker]["quantity"] = new_qty
                    st.session_state.paper_positions[ticker]["avg_price"] = new_avg
                    st.session_state.paper_positions[ticker]["total_cost"] = new_total_cost

                    st.session_state.paper_cash -= total_cost

                    st.session_state.paper_history.append({
                        "Zeit": datetime.now(),
                        "Typ": "Kauf",
                        "Symbol": ticker,
                        "Stück": quantity,
                        "Preis": round(current_price, 2),
                        "Gebühr": round(fee_cost, 2),
                        "Gesamt": round(total_cost, 2)
                    })

                    update_paper_equity_snapshot()

                    # ---------------- AUTO SL / TP / TRAILING ----------------
                    if st.session_state.auto_sl_tp:

                        # Alte Schutzorders für dieses Symbol entfernen
                        st.session_state.paper_open_orders = [
                            order for order in st.session_state.paper_open_orders
                            if not (
                                order["Symbol"] == ticker
                                and order["Order Type"] in ["Stop-Loss", "Take-Profit", "Trailing Stop"]
                            )
                        ]

                        if st.session_state.use_trailing_stop:
                            trailing_anchor = current_price
                            trailing_price = current_price * (
                                1 - st.session_state.trailing_stop_percent / 100
                            )

                            st.session_state.paper_open_orders.append({
                                "Zeit": datetime.now(),
                                "Symbol": ticker,
                                "Order Type": "Trailing Stop",
                                "Stück": quantity,
                                "Limit Price": trailing_price,
                                "Anchor Price": trailing_anchor
                            })

                            st.caption(
                                f"Trailing Stop gesetzt → Stop: {trailing_price:.2f} € | "
                                f"Abstand: {st.session_state.trailing_stop_percent:.2f}%"
                            )
                        else:
                            sl_price = current_price * (1 - st.session_state.auto_sl_percent / 100)
                            tp_price = current_price * (1 + st.session_state.auto_tp_percent / 100)

                            st.session_state.paper_open_orders.append({
                                "Zeit": datetime.now(),
                                "Symbol": ticker,
                                "Order Type": "Stop-Loss",
                                "Stück": quantity,
                                "Limit Price": sl_price
                            })

                            st.session_state.paper_open_orders.append({
                                "Zeit": datetime.now(),
                                "Symbol": ticker,
                                "Order Type": "Take-Profit",
                                "Stück": quantity,
                                "Limit Price": tp_price
                            })

                            st.caption(
                                f"Auto SL/TP gesetzt → SL: {sl_price:.2f} € | TP: {tp_price:.2f} €"
                            )

                    st.success(f"{quantity} Stück {ticker} gekauft.")
                    st.rerun()
                else:
                    st.error("Nicht genug Spielgeld verfügbar.")

            if quick_sell:
                if ticker in st.session_state.paper_positions:
                    position = st.session_state.paper_positions[ticker]
                    held_qty = position["quantity"]
                    quantity = int(quick_trade_qty)

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
                            st.session_state.paper_positions[ticker]["quantity"] = remaining_qty
                            st.session_state.paper_positions[ticker]["total_cost"] = remaining_total_cost
                            st.session_state.paper_positions[ticker]["avg_price"] = remaining_total_cost / remaining_qty
                        else:
                            del st.session_state.paper_positions[ticker]

                        st.session_state.paper_history.append({
                            "Zeit": datetime.now(),
                            "Typ": "Verkauf",
                            "Symbol": ticker,
                            "Stück": quantity,
                            "Preis": round(current_price, 2),
                            "Gebühr": round(fee_cost, 2),
                            "Gesamt": round(total_value, 2),
                            "Realized PnL": round(realized_pnl, 2)
                        })

                        update_paper_equity_snapshot()
                        st.success(f"{quantity} Stück {ticker} verkauft.")
                        st.rerun()
                    else:
                        st.error("Nicht genug Stück vorhanden.")
                else:
                    st.error("Keine Position vorhanden.")

            if quick_sell_all:
                if ticker in st.session_state.paper_positions:
                    position = st.session_state.paper_positions[ticker]
                    quantity = position["quantity"]

                    gross_value = current_price * quantity
                    fee_cost = gross_value * fee_rate
                    total_value = gross_value - fee_cost

                    total_position_cost = position["total_cost"]
                    realized_pnl = total_value - total_position_cost

                    st.session_state.paper_cash += total_value
                    del st.session_state.paper_positions[ticker]

                    st.session_state.paper_history.append({
                        "Zeit": datetime.now(),
                        "Typ": "Verkauf",
                        "Symbol": ticker,
                        "Stück": quantity,
                        "Preis": round(current_price, 2),
                        "Gebühr": round(fee_cost, 2),
                        "Gesamt": round(total_value, 2),
                        "Realized PnL": round(realized_pnl, 2)
                    })

                    update_paper_equity_snapshot()
                    st.success(f"Alle {quantity} Stück {ticker} verkauft.")
                    st.rerun()
                else:
                    st.error("Keine Position vorhanden.")

            st.markdown("---")
            st.write("### 🎯 Limit Orders")

            limit_col1, limit_col2, limit_col3, limit_col4 = st.columns([1, 1, 1, 1])

            with limit_col1:
                limit_order_type = st.selectbox(
                    "Order-Typ",
                    ["Limit Buy", "Limit Sell", "Stop-Loss", "Take-Profit"],
                    key=f"limit_order_type_{ticker}"
                )

            with limit_col2:
                limit_order_qty = st.number_input(
                    "Stück",
                    min_value=1,
                    value=1,
                    step=1,
                    key=f"limit_order_qty_{ticker}"
                )

            with limit_col3:
                limit_order_price = st.number_input(
                    "Limit Preis",
                    min_value=0.01,
                    value=float(data["Close"].iloc[-1]),
                    step=0.1,
                    key=f"limit_order_price_{ticker}"
                )

            with limit_col4:
                place_limit_order = st.button("📌 Order setzen", key=f"place_limit_order_{ticker}")

            if place_limit_order:
                st.session_state.paper_open_orders.append({
                    "Zeit": datetime.now(),
                    "Symbol": ticker,
                    "Order Type": limit_order_type,
                    "Stück": int(limit_order_qty),
                    "Limit Price": float(limit_order_price)
                })

                st.success(
                    f"{limit_order_type} für {ticker} gesetzt: "
                    f"{int(limit_order_qty)} Stück bei {float(limit_order_price):.2f} €"
                )
                st.rerun()

            st.write("### Candlestick-Chart mit EMA + Fibonacci + Volumen")
            st.caption(f"Aktives Theme: {chart_theme}")
            st.caption(f"Aktueller Preis: {current_price:.2f}")

            col1, col2, col3, col4 = st.columns([1,1,1,2])

            if buy_button:
                total_cost = current_price * trade_quantity
                fee_cost = total_cost * fee_rate
                total_cost_with_fee = total_cost + fee_cost

                if st.session_state.paper_cash >= total_cost_with_fee:

                    if ticker not in st.session_state.paper_positions:
                        st.session_state.paper_positions[ticker] = {
                            "quantity": 0,
                            "avg_price": 0.0,
                            "total_cost": 0.0
                        }

                    pos = st.session_state.paper_positions[ticker]

                    new_qty = pos["quantity"] + trade_quantity
                    new_total_cost = pos["total_cost"] + total_cost_with_fee
                    new_avg = new_total_cost / new_qty

                    pos["quantity"] = new_qty
                    pos["avg_price"] = new_avg
                    pos["total_cost"] = new_total_cost

                    st.session_state.paper_cash -= total_cost_with_fee

                    st.success(f"BUY {trade_quantity}x {ticker} @ {current_price:.2f}")

                else:
                    st.error("Nicht genug Kapital")

            if sell_button:

                if ticker in st.session_state.paper_positions:
                    pos = st.session_state.paper_positions[ticker]

                    if pos["quantity"] >= trade_quantity:

                        gross_value = current_price * trade_quantity
                        fee_cost = gross_value * fee_rate
                        total_value = gross_value - fee_cost

                        avg_price = pos["avg_price"]
                        cost_basis = avg_price * trade_quantity
                        realized_pnl = total_value - cost_basis

                        st.session_state.paper_cash += total_value

                        remaining_qty = pos["quantity"] - trade_quantity
                        remaining_cost = pos["total_cost"] - cost_basis

                        if remaining_qty > 0:
                            pos["quantity"] = remaining_qty
                            pos["total_cost"] = remaining_cost
                            pos["avg_price"] = remaining_cost / remaining_qty
                        else:
                            del st.session_state.paper_positions[ticker]

                        st.success(
                            f"SELL {trade_quantity}x {ticker} | PnL: {realized_pnl:.2f}"
                        )

                    else:
                        st.warning("Nicht genug Stücke")

                else:
                    st.warning("Keine Position vorhanden")

            if show_volume:
                fig = make_subplots(
                    rows=2,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    row_heights=[0.7, 0.3]
                )
            else:
                fig = make_subplots(
                    rows=1,
                    cols=1
                )

            # Candlestick
            fig.add_trace(
                go.Candlestick(
                    x=data.index,
                    open=data["Open"],
                    high=data["High"],
                    low=data["Low"],
                    close=data["Close"],
                    name="Price",
                    increasing_line_color="#26a69a",
                    increasing_fillcolor="#26a69a",
                    decreasing_line_color="#ef5350",
                    decreasing_fillcolor="#ef5350",
                    increasing_line_width=1,
                    decreasing_line_width=1,
                    opacity=0.95
                ),
                row=1, col=1
            )

            # EMA
            if show_ema:
                fig.add_trace(
                    go.Scatter(
                        x=data.index,
                        y=data["EMA20"],
                        name="EMA20",
                        line=dict(width=1.4, color="#ffd54f")
                    ),
                    row=1, col=1
                )

                fig.add_trace(
                    go.Scatter(
                        x=data.index,
                        y=data["EMA50"],
                        name="EMA50",
                        line=dict(width=1.4, color="#64b5f6")
                    ),
                    row=1, col=1
                )

                fig.add_trace(
                    go.Scatter(
                        x=data.index,
                        y=data["EMA200"],
                        name="EMA200",
                        line=dict(width=1.5, color="#ba68c8")
                    ),
                    row=1, col=1
                )

            paper_history_df = pd.DataFrame(st.session_state.paper_history)
            paper_trade_lines = []

            if not paper_history_df.empty and "Zeit" in paper_history_df.columns:
                sorted_history = paper_history_df.sort_values("Zeit").copy()

                open_buys = []

                for _, row in sorted_history.iterrows():
                    if row["Typ"] == "Kauf":
                        open_buys.append(row)

                    elif row["Typ"] == "Verkauf" and open_buys:
                        buy_row = open_buys.pop(0)

                        entry_price = float(buy_row["Preis"])
                        exit_price = float(row["Preis"])

                        pnl_color = "#66bb6a" if exit_price > entry_price else "#ef5350"

                        paper_trade_lines.append({
                            "entry_time": buy_row["Zeit"],
                            "exit_time": row["Zeit"],
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "color": pnl_color,
                            "quantity": row.get("Stück", 0),
                            "pnl": row.get("Realized PnL", 0)
                        })

            if not paper_history_df.empty:
                paper_history_df = paper_history_df[paper_history_df["Symbol"] == ticker].copy()

                if "Zeit" in paper_history_df.columns:
                    paper_history_df["Zeit"] = pd.to_datetime(paper_history_df["Zeit"], errors="coerce")

                paper_buys_df = paper_history_df[paper_history_df["Typ"] == "Kauf"].copy()
                paper_sells_df = paper_history_df[paper_history_df["Typ"] == "Verkauf"].copy()
            else:
                paper_buys_df = pd.DataFrame()
                paper_sells_df = pd.DataFrame()

            open_orders_df = pd.DataFrame(st.session_state.paper_open_orders)

            if not open_orders_df.empty:
                open_orders_df = open_orders_df[open_orders_df["Symbol"] == ticker].copy()

                stop_loss_orders_df = open_orders_df[
                    open_orders_df["Order Type"] == "Stop-Loss"
                ].copy()

                take_profit_orders_df = open_orders_df[
                    open_orders_df["Order Type"] == "Take-Profit"
                ].copy()

                trailing_stop_orders_df = open_orders_df[
                    open_orders_df["Order Type"] == "Trailing Stop"
                ].copy()
            else:
                stop_loss_orders_df = pd.DataFrame()
                take_profit_orders_df = pd.DataFrame()
                trailing_stop_orders_df = pd.DataFrame()

            # BUY Marker
            if show_trade_markers and not buy_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=buy_df["Date"],
                        y=buy_df["Price"],
                        mode="markers",
                        name="Buy",
                        marker=dict(color="#26a69a", size=8, symbol="triangle-up")
                    ),
                    row=1, col=1
                )

            # Sell Marker (verschiedene Exit-Typen)
            if show_trade_markers and not sell_df.empty:
                for _, row in sell_df.iterrows():

                    exit_type = row.get("Type", "Sell")

                    if exit_type == "Stop-Loss":
                        color = "#ef5350"
                        symbol = "x"

                    elif exit_type == "Take-Profit":
                        color = "#66bb6a"
                        symbol = "star"

                    elif exit_type == "EMA Exit":
                        color = "#ffa726"
                        symbol = "diamond"

                    else:
                        color = "#bdbdbd"
                        symbol = "circle"

                    fig.add_trace(
                        go.Scatter(
                            x=[row["Date"]],
                            y=[row["Price"]],
                            mode="markers",
                            marker=dict(
                                color=color,
                                size=8,
                                symbol=symbol,
                                opacity=0.9
                            ),
                            name=exit_type,
                            showlegend=False
                        ),
                        row=1, col=1
                    )

            if show_paper_markers and not paper_buys_df.empty and "Zeit" in paper_buys_df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=paper_buys_df["Zeit"],
                        y=paper_buys_df["Preis"],
                        mode="markers",
                        name="Paper BUY",
                        marker=dict(
                            color="#00c2ff",
                            size=10,
                            symbol="triangle-up",
                            line=dict(width=0.8, color="#111")
                        ),
                        hovertemplate=(
                            "Paper BUY<br>"
                            "Zeit: %{x}<br>"
                            "Preis: %{y:.2f}<extra></extra>"
                        )
                    ),
                    row=1, col=1
                )

            if show_paper_markers and not paper_sells_df.empty and "Zeit" in paper_sells_df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=paper_sells_df["Zeit"],
                        y=paper_sells_df["Preis"],
                        mode="markers",
                        name="Paper SELL",
                        marker=dict(
                            color="#ff4fc3",
                            size=10,
                            symbol="triangle-down",
                            line=dict(width=0.8, color="#111")
                        ),
                        hovertemplate=(
                            "Paper SELL<br>"
                            "Zeit: %{x}<br>"
                            "Preis: %{y:.2f}<extra></extra>"
                        )
                    ),
                    row=1, col=1
                )

            if show_paper_markers and paper_trade_lines:
                for trade_line in paper_trade_lines:
                    fig.add_trace(
                        go.Scatter(
                            x=[trade_line["entry_time"], trade_line["exit_time"]],
                            y=[trade_line["entry_price"], trade_line["exit_price"]],
                            mode="lines",
                            name="Paper Trade",
                            line=dict(
                                color=trade_line["color"],
                                width=1.5,
                                dash="solid"
                            ),
                            showlegend=False,
                            hovertemplate=(
                                "Paper Trade<br>"
                                f"Entry: {trade_line['entry_price']:.2f}<br>"
                                f"Exit: {trade_line['exit_price']:.2f}<br>"
                                f"Stück: {trade_line['quantity']}<br>"
                                f"PnL: {trade_line['pnl']:.2f}<extra></extra>"
                            )
                        ),
                        row=1, col=1
                    )

            # Trade Linien
            if show_trade_markers and not trades_df.empty:
                for _, trade in trades_df.iterrows():
                    color = "green" if trade["Exit Price"] > trade["Entry Price"] else "red"

                    fig.add_trace(
                        go.Scatter(
                            x=[trade["Entry Date"], trade["Exit Date"]],
                            y=[trade["Entry Price"], trade["Exit Price"]],
                            mode="lines",
                            line=dict(color=color, width=1, dash="dot"),
                            showlegend=False
                        ),
                        row=1, col=1
                    )

            # Fibonacci
            if show_fibonacci:
                for name, value in fib_levels.items():
                    fig.add_hline(y=value, line_dash="dash", line_width=0.8)

            # Support / Resistance
            if show_support_resistance:
                for s in supports:
                    fig.add_hline(y=s, line_dash="dot", line_width=0.8)

                for r in resistances:
                    fig.add_hline(y=r, line_dash="dot", line_width=0.8)

            # Volume
            if show_volume:
                fig.add_trace(
                    go.Bar(
                        x=data.index,
                        y=data["Volume"],
                        name="Volumen",
                        marker=dict(color=volume_color)
                    ),
                    row=2, col=1
                )

            chart_height = 520 if show_volume else 420

            fig.update_layout(
                height=chart_height,
                dragmode="pan",
                xaxis_rangeslider_visible=True,
                hovermode="x unified",

                # ❌ Template deaktiviert
                # template=chart_template,

                plot_bgcolor=chart_bg,
                paper_bgcolor=paper_bg,

                font=dict(color=font_color),

                xaxis=dict(
                    gridcolor="rgba(120, 180, 255, 0.08)",
                    zerolinecolor="rgba(120, 180, 255, 0.08)"
                ),
                yaxis=dict(
                    gridcolor="rgba(120, 180, 255, 0.08)",
                    zerolinecolor="rgba(120, 180, 255, 0.08)"
                ),

                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0
                ),

                margin=dict(l=20, r=20, t=40, b=20)
            )

            fig.update_xaxes(matches="x")

            fig.update_xaxes(
                showgrid=True,
                gridcolor=grid_color,
                zeroline=False,
                showline=False
            )

            fig.update_yaxes(
                showgrid=True,
                gridcolor=grid_color,
                zeroline=False,
                showline=False
            )

            if ticker in st.session_state.paper_positions:
                pos = st.session_state.paper_positions[ticker]

                current_price = float(data["Close"].iloc[-1])
                quantity = pos["quantity"]
                avg_price = pos["avg_price"]
                total_cost = pos.get("total_cost", quantity * avg_price)

                market_value = quantity * current_price
                open_pnl = market_value - total_cost
                open_pnl_pct = (open_pnl / total_cost * 100) if total_cost > 0 else 0

                pnl_color = "#26a69a" if open_pnl > 0 else "#ef5350" if open_pnl < 0 else "#9e9e9e"
                annotation_font_color = "white" if chart_theme == "Dark" else "#111111"

                fig.add_annotation(
                    xref="paper",
                    yref="paper",
                    x=0.01,
                    y=0.98,
                    text=f"{ticker} | {open_pnl:.2f} € | {open_pnl_pct:.2f}%",
                    showarrow=False,
                    font=dict(size=12, color=annotation_font_color),
                    align="left",
                    bgcolor=pnl_color,
                    bordercolor=pnl_color,
                    borderwidth=1,
                    borderpad=6,
                    opacity=0.9
                )

            if show_sl_tp_orders and not stop_loss_orders_df.empty:
                for _, order in stop_loss_orders_df.iterrows():
                    sl_price = float(order["Limit Price"])

                    fig.add_hline(
                        y=sl_price,
                        line_dash="dot",
                        line_width=1.2,
                        line_color="#ef5350",
                        annotation_text=f"SL {sl_price:.2f}",
                        annotation_position="right"
                    )

            if show_sl_tp_orders and not take_profit_orders_df.empty:
                for _, order in take_profit_orders_df.iterrows():
                    tp_price = float(order["Limit Price"])

                    fig.add_hline(
                        y=tp_price,
                        line_dash="dot",
                        line_width=1.2,
                        line_color="#26a69a",
                        annotation_text=f"TP {tp_price:.2f}",
                        annotation_position="right"
                    )

            if show_sl_tp_orders and not trailing_stop_orders_df.empty:
                for _, order in trailing_stop_orders_df.iterrows():
                    ts_price = float(order["Limit Price"])

                    fig.add_hline(
                        y=ts_price,
                        line_dash="dash",
                        line_width=1.4,
                        line_color="#ff9800",
                        annotation_text=f"TS {ts_price:.2f}",
                        annotation_position="right"
                    )

            st.plotly_chart(
                fig,
                width="stretch",
                config={
                    "scrollZoom": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"]
                }
            )

            # RSI & MACD
            st.write("### RSI")
            st.line_chart(data[["RSI"]].dropna())

            st.write("### MACD")
            st.line_chart(data[["MACD", "MACD_SIGNAL"]].dropna())
            st.markdown("---")

            # ---------------- BACKTEST ----------------
            st.write("### Backtesting")

            st.caption("Simulation historischer Trades auf Basis deiner aktuellen Strategie-Einstellungen. Keine Garantie für zukünftige Ergebnisse.")

            if trades_df.empty:
                st.info("Keine Trades im Zeitraum.")
            else:
                st.dataframe(trades_df, width="stretch")

                total_return = ((equity_df["Equity"].iloc[-1] / 1000) - 1) * 100
                avg_return = trades_df["Trade Return After Fees %"].mean()
                win_rate = (trades_df["Trade Return After Fees %"] > 0).mean() * 100
                max_dd = calculate_max_drawdown(equity_df)

                wins = trades_df[trades_df["Trade Return After Fees %"] > 0]
                losses = trades_df[trades_df["Trade Return After Fees %"] < 0]

                trade_col = "Trade Return After Fees %"

                if trade_col in trades_df.columns:
                    wins = trades_df[trades_df[trade_col] > 0]
                    losses = trades_df[trades_df[trade_col] < 0]

                    avg_win = wins[trade_col].mean() if not wins.empty else 0
                    avg_loss = losses[trade_col].mean() if not losses.empty else 0
                else:
                    avg_win = 0
                    avg_loss = 0

                total_profit = wins["Trade Return After Fees %"].sum() if not wins.empty else 0
                total_loss = abs(losses["Trade Return After Fees %"].sum()) if not losses.empty else 0

                profit_factor = total_profit / total_loss if total_loss > 0 else 0

                st.write("### 📈 Ergebnisse")

                st.caption(
                    f"Gebühren: {fee_percent:.2f}% | "
                    f"Stop-Loss: {stop_loss_percent:.2f}% | "
                    f"Take-Profit: {take_profit_percent:.2f}% | "
                    f"RSI Filter: {'AN' if use_rsi_filter else 'AUS'} "
                    f"({rsi_min:.0f} bis {rsi_max:.0f}) | "
                    f"EMA200 Filter: {'AN' if use_ema200_filter else 'AUS'}"
                )

                c1, c2, c3, c4, c5, c6, c7 = st.columns(7)

                c1.metric("Trades", len(trades_df))
                c2.metric("Ø Trade", f"{avg_return:.2f}%")
                c3.metric("Trefferquote", f"{win_rate:.1f}%")
                c4.metric("Gesamtrendite", f"{total_return:.2f}%")
                c5.metric("Max Drawdown", f"{max_dd:.2f}%")
                c6.metric("Ø Gewinntrade", f"{avg_win:.2f}%")
                c7.metric("Ø Verlusttrade", f"{abs(avg_loss):.2f}%")

                st.write(f"**Profit Factor:** {profit_factor:.2f}")

                st.write("### ⚖️ Strategie Vergleich: EMA + RSI vs EMA ohne RSI")

                def calc_stats(trades_df, equity_df):
                    if trades_df.empty or equity_df.empty:
                        return 0, 0, 0

                    total_return = ((equity_df["Equity"].iloc[-1] / 1000) - 1) * 100
                    win_rate = (trades_df["Trade Return After Fees %"] > 0).mean() * 100
                    avg_return = trades_df["Trade Return After Fees %"].mean()

                    return total_return, win_rate, avg_return

                ret1, win1, avg1 = calc_stats(trades_df, equity_df)
                ret2, win2, avg2 = calc_stats(trades_df_no_rsi, equity_df_no_rsi)

                c1, c2 = st.columns(2)

                with c1:
                    st.subheader("EMA + RSI")
                    st.metric("Return", f"{ret1:.2f}%")
                    st.metric("Win Rate", f"{win1:.1f}%")
                    st.metric("Ø Trade", f"{avg1:.2f}%")

                with c2:
                    st.subheader("EMA ohne RSI")
                    st.metric("Return", f"{ret2:.2f}%")
                    st.metric("Win Rate", f"{win2:.1f}%")
                    st.metric("Ø Trade", f"{avg2:.2f}%")

                st.write("### 📈 Equity Curve Vergleich")

                fig_compare = go.Figure()

                if not equity_df.empty:
                    fig_compare.add_trace(go.Scatter(
                        x=equity_df["Date"],
                        y=equity_df["Equity"],
                        name="EMA + RSI"
                    ))

                if not equity_df_no_rsi.empty:
                    fig_compare.add_trace(go.Scatter(
                        x=equity_df_no_rsi["Date"],
                        y=equity_df_no_rsi["Equity"],
                        name="EMA ohne RSI"
                    ))

                fig_compare.update_layout(
                    height=400,
                    hovermode="x unified"
                )

                st.plotly_chart(fig_compare, width="stretch")
                st.markdown("---")

                st.write("### 🧪 Parameter-Test")
                st.caption("Hier testet Emanacci verschiedene Kombinationen aus Stop-Loss, Take-Profit, RSI und weiteren Filtern, um bessere Einstellungen zu finden.")
                st.caption(
                    "Der Optimierungs-Score kombiniert Return, Profit Factor, Win Rate und Drawdown. "
                    "Die Gewichtungen kannst du links in der Sidebar anpassen."
                )

                optimization_target = st.selectbox(
                    "Optimieren nach",
                    ["Return %", "Profit Factor", "Win Rate %", "Max Drawdown %", "Optimierungs-Score"],
                    index=0
                )

                heatmap_metric = st.selectbox(
                    "Heatmap anzeigen für",
                    ["Return %", "Profit Factor", "Win Rate %", "Max Drawdown %", "Optimierungs-Score"],
                    index=0
                )

                st.caption(
                    f"SL-Werte: {optimization_sl_input} | "
                    f"TP-Werte: {optimization_tp_input} | "
                    f"RSI-Bereiche: {optimization_rsi_input}"
                )

                run_optimization = st.button("Optimierung starten")

                reset_optimization = st.button("Optimierung zurücksetzen")

                if reset_optimization:
                    st.session_state.optimization_df = pd.DataFrame()
                    st.session_state.optimization_finished = False

                if run_optimization:
                    with st.spinner("Optimierung läuft..."):
                        stop_loss_values = parse_float_list(optimization_sl_input)
                        take_profit_values = parse_float_list(optimization_tp_input)

                        if use_rsi_filter:
                            rsi_ranges = parse_rsi_ranges(optimization_rsi_input)
                        else:
                            rsi_ranges = [(rsi_min, rsi_max)]

                        if not stop_loss_values:
                            stop_loss_values = [3.0, 5.0, 7.0]

                        if not take_profit_values:
                            take_profit_values = [6.0, 10.0, 15.0]

                        if use_rsi_filter and not rsi_ranges:
                            rsi_ranges = [(35.0, 75.0), (40.0, 70.0), (45.0, 65.0)]

                        ema200_options = [False, True]

                        optimization_results = []

                        total_runs = len(stop_loss_values) * len(take_profit_values) * len(rsi_ranges) * len(ema200_options)
                        current_run = 0

                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        for sl in stop_loss_values:
                            for tp in take_profit_values:
                                for rsi_min_opt, rsi_max_opt in rsi_ranges:
                                    for ema200_opt in ema200_options:
                                        current_run += 1

                                        status_text.text(
                                            f"Teste Kombination {current_run}/{total_runs} | "
                                            f"SL {sl}% | TP {tp}% | RSI {rsi_min_opt}-{rsi_max_opt} | "
                                            f"EMA200 {'AN' if ema200_opt else 'AUS'}"
                                        )

                                        opt_trades, opt_equity, _, _ = backtest_ema_strategy(
                                            data,
                                            initial_capital=1000,
                                            fee_percent=fee_percent,
                                            stop_loss_percent=sl,
                                            take_profit_percent=tp,
                                            use_rsi_filter=use_rsi_filter,
                                            rsi_min=rsi_min_opt,
                                            rsi_max=rsi_max_opt,
                                            use_ema200_filter=ema200_opt
                                        )

                                        stats = calc_stats_for_optimization(opt_trades, opt_equity)

                                        optimization_results.append({
                                            "Stop-Loss %": sl,
                                            "Take-Profit %": tp,
                                            "RSI Min": rsi_min_opt,
                                            "RSI Max": rsi_max_opt,
                                            "EMA200 Filter": "AN" if ema200_opt else "AUS",
                                            **stats
                                        })

                                        progress_bar.progress(current_run / total_runs)

                        status_text.text("Optimierung abgeschlossen.")

                        optimization_df = pd.DataFrame(optimization_results)

                        st.session_state.optimization_df = optimization_df
                        st.session_state.optimization_finished = True

                optimization_df = st.session_state.optimization_df

                if st.session_state.optimization_finished and not optimization_df.empty:
                    optimization_df = optimization_df.copy()

                    optimization_df["Optimierungs-Score"] = (
                        optimization_df["Return %"] * score_weight_return
                        + optimization_df["Profit Factor"] * score_weight_pf
                        + optimization_df["Win Rate %"] * score_weight_winrate
                        - optimization_df["Max Drawdown %"].abs() * score_weight_drawdown
                    )

                    if optimization_target == "Max Drawdown %":
                        optimization_df["Drawdown Score"] = optimization_df["Max Drawdown %"].abs()
                        optimization_df = optimization_df.sort_values(
                            by="Drawdown Score",
                            ascending=True
                        ).reset_index(drop=True)
                    else:
                        optimization_df = optimization_df.sort_values(
                            by=optimization_target,
                            ascending=False
                        ).reset_index(drop=True)

                    display_df = optimization_df.copy()

                    if "Drawdown Score" in display_df.columns:
                        display_df = display_df.drop(columns=["Drawdown Score"])

                    st.caption(f"Sortiert nach: {optimization_target}")

                    preferred_columns = [
                        "Stop-Loss %",
                        "Take-Profit %",
                        "RSI Min",
                        "RSI Max",
                        "EMA200 Filter",
                        "Return %",
                        "Profit Factor",
                        "Win Rate %",
                        "Max Drawdown %",
                        "Optimierungs-Score",
                        "Trades",
                    ]

                    existing_columns = [col for col in preferred_columns if col in display_df.columns]
                    display_df = display_df[existing_columns]
                    display_df = display_df.round(2)

                    st.dataframe(display_df, width="stretch")

                    optimization_csv = display_df.to_csv(index=False).encode("utf-8")

                    st.download_button(
                        label="📥 Optimierung als CSV herunterladen",
                        data=optimization_csv,
                        file_name=(
                            f"optimierung_{ticker}_{period}_{interval}_"
                            f"{optimization_target.replace(' ', '_').replace('%', 'pct')}.csv"
                        ),
                        mime="text/csv"
                    )

                    best_csv = display_df.head(1).to_csv(index=False).encode("utf-8")

                    st.download_button(
                        label="🏆 Bestes Ergebnis als CSV herunterladen",
                        data=best_csv,
                        file_name=f"bestes_ergebnis_{ticker}_{period}_{interval}.csv",
                        mime="text/csv"
                    )

                    best_row = optimization_df.iloc[0]

                    if optimization_target == "Max Drawdown %":
                        best_value_text = f"{best_row['Max Drawdown %']}%"
                    else:
                        best_value_text = f"{best_row[optimization_target]}"

                    st.success(
                        f"Beste Kombination nach {optimization_target}: "
                        f"SL {best_row['Stop-Loss %']}% | "
                        f"TP {best_row['Take-Profit %']}% | "
                        f"RSI {best_row['RSI Min']}–{best_row['RSI Max']} | "
                        f"EMA200 {best_row['EMA200 Filter']} | "
                        f"Wert: {best_value_text}"
                    )

                    apply_best_params = st.button("✅ Beste Parameter anwenden")

                    if apply_best_params:
                        st.session_state["stop_loss_percent"] = float(best_row["Stop-Loss %"])
                        st.session_state["take_profit_percent"] = float(best_row["Take-Profit %"])
                        st.session_state["rsi_min"] = float(best_row["RSI Min"])
                        st.session_state["rsi_max"] = float(best_row["RSI Max"])
                        st.session_state["use_rsi_filter"] = True
                        st.session_state["use_ema200_filter"] = True if best_row["EMA200 Filter"] == "AN" else False
                        st.rerun()

                    st.caption(
                        f"Gewichte → Return: {score_weight_return:.1f} | "
                        f"Profit Factor: {score_weight_pf:.1f} | "
                        f"Win Rate: {score_weight_winrate:.1f} | "
                        f"Drawdown: {score_weight_drawdown:.1f}"
                    )

                    st.write("### 🌡️ Optimierungs-Heatmap")

                    heatmap_source_df = optimization_df.copy()

                    if optimization_target == "Max Drawdown %":
                        heatmap_source_df["Sort Metric"] = heatmap_source_df["Max Drawdown %"].abs()
                        heatmap_source_df = heatmap_source_df.sort_values(
                        ["Stop-Loss %", "Take-Profit %", "Sort Metric"],
                            ascending=[True, True, True]
                        )
                    else:
                        heatmap_source_df = heatmap_source_df.sort_values(
                            ["Stop-Loss %", "Take-Profit %", optimization_target],
                            ascending=[True, True, False]
                        )

                    heatmap_source_df = heatmap_source_df.drop_duplicates(
                        subset=["Stop-Loss %", "Take-Profit %"],
                        keep="first"
                    )

                    heatmap_metric_for_values = heatmap_metric

                    if heatmap_metric_for_values == "Max Drawdown %":
                        heatmap_df = heatmap_source_df.pivot(
                            index="Stop-Loss %",
                            columns="Take-Profit %",
                            values="Max Drawdown %"
                        )
                    else:
                        heatmap_df = heatmap_source_df.pivot(
                            index="Stop-Loss %",
                            columns="Take-Profit %",
                            values=heatmap_metric_for_values
                        )

                    heatmap_fig = go.Figure(
                        data=go.Heatmap(
                            z=heatmap_df.values,
                            x=heatmap_df.columns,
                            y=heatmap_df.index,
                            text=heatmap_df.round(2).values,
                            texttemplate="%{text}",
                            textfont={"size": 12},
                            hovertemplate=(
                                "Stop-Loss: %{y}%<br>"
                                "Take-Profit: %{x}%<br>"
                                "Wert: %{z:.2f}<extra></extra>"
                            )
                        )
                    )

                    heatmap_fig.update_layout(
                        height=500,
                        xaxis_title="Take-Profit %",
                        yaxis_title="Stop-Loss %"
                    )

                    st.plotly_chart(heatmap_fig, width="stretch")

        # ---------------- VERGLEICH ----------------
        with tab_vergleich:
            st.write("### Vergleich")

            symbols = [s.strip().upper() for s in compare_input.split(",") if s.strip()]
            compare_df = pd.DataFrame()

            for sym in symbols:
                d = load_data(sym, period, interval)
                if d.empty:
                    continue

                d["Close"] = pd.to_numeric(d["Close"], errors="coerce")
                d = d.dropna()

                base = d["Close"].iloc[0]
                compare_df[sym] = (d["Close"] / base) * 100

            if compare_df.empty:
                st.info("Keine Daten")
            else:
                fig2 = go.Figure()

                for col in compare_df.columns:
                    fig2.add_trace(go.Scatter(x=compare_df.index, y=compare_df[col], name=col))

                st.plotly_chart(
                    fig,
                    width="stretch",
                    config={
                        "scrollZoom": True,
                        "displaylogo": False,
                        "modeBarButtonsToRemove": [
                            "lasso2d",
                            "select2d",
                            "zoomIn2d",
                            "zoomOut2d",
                            "autoScale2d"
                        ]
                    }
                )