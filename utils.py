import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf


WATCHLIST_FILE = Path("watchlist.json")
USER_SETTINGS_FILE = Path("user_settings.json")
JOURNAL_NOTES_FILE = Path("trade_journal_notes.json")


def load_trade_journal_notes() -> dict:
    if JOURNAL_NOTES_FILE.exists():
        try:
            with open(JOURNAL_NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return {}


def save_trade_journal_notes(notes: dict):
    try:
        with open(JOURNAL_NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Trade Journal Notes konnten nicht gespeichert werden: {e}")


@st.cache_data(show_spinner=False, ttl=300)
def load_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    symbol = str(symbol).upper().strip()
    period = str(period).strip()
    interval = str(interval).strip()

    data = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False
    )

    if data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    required_cols = ["Open", "High", "Low", "Close"]
    data = data.dropna(subset=required_cols)

    return data.copy()


def filter_levels(levels, min_distance_percent: float = 0.01):
    filtered = []

    for level in sorted(levels):
        if not filtered:
            filtered.append(level)
        else:
            too_close = False
            for existing in filtered:
                if abs(level - existing) / existing < min_distance_percent:
                    too_close = True
                    break
            if not too_close:
                filtered.append(level)

    return filtered


def load_watchlist():
    if WATCHLIST_FILE.exists():
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                cleaned = [str(item).upper().strip() for item in data if str(item).strip()]
                return cleaned if cleaned else ["TSLA", "AAPL", "NVDA"]
        except Exception:
            pass

    return ["TSLA", "AAPL", "NVDA"]


def save_watchlist(watchlist):
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Watchlist konnte nicht gespeichert werden: {e}")


def calculate_max_drawdown(equity_df: pd.DataFrame) -> float:
    if equity_df.empty or "Equity" not in equity_df.columns:
        return 0.0

    equity_series = equity_df["Equity"].copy()
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max * 100

    return drawdown.min()


def load_user_settings():
    if USER_SETTINGS_FILE.exists():
        try:
            with open(USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return {}


def save_user_settings(settings: dict):
    try:
        with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"User Settings konnten nicht gespeichert werden: {e}")