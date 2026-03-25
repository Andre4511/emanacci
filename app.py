import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
from pathlib import Path
from plotly.subplots import make_subplots


def calculate_indicators(data):
    data = data.copy()

    # EMA
    data["EMA20"] = data["Close"].ewm(span=20).mean()
    data["EMA50"] = data["Close"].ewm(span=50).mean()

    # RSI
    delta = data["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()

    rs = avg_gain / avg_loss
    data["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = data["Close"].ewm(span=12).mean()
    ema26 = data["Close"].ewm(span=26).mean()
    data["MACD"] = ema12 - ema26
    data["MACD_SIGNAL"] = data["MACD"].ewm(span=9).mean()
    data["MACD_HIST"] = data["MACD"] - data["MACD_SIGNAL"]

    return data


def load_data(symbol, period, interval):
    data = yf.download(symbol, period=period, interval=interval, auto_adjust=True)

    if data.empty:
        return data

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    required_cols = ["Open", "High", "Low", "Close"]
    data = data.dropna(subset=required_cols)

    return data


def filter_levels(levels, min_distance_percent=0.01):
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

WATCHLIST_FILE = Path("watchlist.json")


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


st.title("📈 Trading App")
st.caption("Technische Marktanalyse mit EMA, RSI, MACD, Fibonacci, Support/Resistance und Vergleich mehrerer Werte.")

def backtest_ema_strategy(data, initial_capital=1000, fee_percent=0.1):
    data = data.copy()

    position = 0
    shares = 0.0
    entry_price = 0.0
    capital = initial_capital
    entry_capital_after_fee = 0.0

    trades = []
    equity_history = []
    buy_markers = []
    sell_markers = []

    fee_rate = fee_percent / 100

    for i in range(1, len(data)):
        prev = data.iloc[i - 1]
        curr = data.iloc[i]
        current_date = curr.name
        current_close = curr["Close"]

        # BUY Signal
        if position == 0 and prev["EMA20"] <= prev["EMA50"] and curr["EMA20"] > curr["EMA50"]:
            position = 1
            entry_price = current_close
            entry_date = current_date

            entry_fee = capital * fee_rate
            entry_capital_after_fee = capital - entry_fee
            shares = entry_capital_after_fee / current_close

            buy_markers.append({
                "Date": current_date,
                "Price": current_close
            })

        # SELL Signal
        elif position == 1 and prev["EMA20"] >= prev["EMA50"] and curr["EMA20"] < curr["EMA50"]:
            exit_price = current_close
            exit_date = current_date

            gross_exit_value = shares * exit_price
            exit_fee = gross_exit_value * fee_rate
            capital = gross_exit_value - exit_fee

            trade_return_pct = ((exit_price - entry_price) / entry_price) * 100
            trade_return_after_fees_pct = ((capital / entry_capital_after_fee) - 1) * 100 if entry_capital_after_fee > 0 else 0

            trades.append({
                "Entry Date": entry_date,
                "Exit Date": exit_date,
                "Entry Price": round(entry_price, 2),
                "Exit Price": round(exit_price, 2),
                "Trade Return %": round(trade_return_pct, 2),
                "Trade Return After Fees %": round(trade_return_after_fees_pct, 2),
                "Capital After Trade": round(capital, 2)
            })

            sell_markers.append({
                "Date": current_date,
                "Price": current_close
            })

            position = 0
            shares = 0.0
            entry_capital_after_fee = 0.0

        # Equity berechnen
        if position == 1:
            equity = shares * current_close
        else:
            equity = capital

        equity_history.append({
            "Date": current_date,
            "Equity": equity
        })

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_history)
    buy_df = pd.DataFrame(buy_markers)
    sell_df = pd.DataFrame(sell_markers)

    return trades_df, equity_df, buy_df, sell_df

# Watchlist initialisieren
if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

with st.sidebar:
    st.header("⚙️ Einstellungen")

    selected_watch_symbol = st.selectbox(
        "Symbol aus Watchlist wählen",
        st.session_state.watchlist
    )

    ticker = st.text_input(
        "Aktie eingeben (z. B. AAPL, TSLA, MSFT, BTC-USD)",
        selected_watch_symbol
    ).upper()

    compare_input = st.text_input(
        "Vergleichssymbole (mit Komma trennen)",
        "TSLA, AAPL, NVDA"
    )

    period = st.selectbox(
        "Zeitraum wählen",
        ["5d", "1mo", "3mo", "6mo", "1y"],
        index=2
    )

    interval = st.selectbox(
        "Intervall wählen",
        ["15m", "1h", "1d"],
        index=2
    )

    fee_percent = st.number_input(
        "Gebühr pro Kauf/Verkauf (%)",
        min_value=0.0,
        max_value=5.0,
        value=0.1,
        step=0.05
    )

    st.caption("Tipp: Für 15m sind meist nur 5d oder 1mo sinnvoll.")
    st.markdown("---")
    st.write("### Schnellhilfe")
    st.write("- 15m eher für kurzfristige Analyse")
    st.write("- 1h für Swing-/Kurzfrist-Trends")
    st.write("- 1d für mittelfristige Analyse")

tab_analyse, tab_vergleich, tab_watchlist = st.tabs(
    ["📈 Einzelanalyse", "📊 Vergleich", "⭐ Watchlist"]
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

invalid_combo = False

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

        # Fibonacci-Level aus Hoch und Tief des sichtbaren Bereichs
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

        # Support / Resistance grob erkennen
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
            fee_percent=fee_percent
        )

        with tab_analyse:
            st.write("### Letzte Kursdaten")
            st.caption("Die letzten geladenen Marktdaten für das ausgewählte Symbol.")
            st.dataframe(data.tail())

            st.write("### Candlestick-Chart mit EMA + Fibonacci + Volumen")

            fig = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=[0.7, 0.3]
            )

            # Candlestick (oben)
            fig.add_trace(
                go.Candlestick(
                    x=data.index,
                    open=data["Open"],
                    high=data["High"],
                    low=data["Low"],
                    close=data["Close"],
                    name="Kerzen"
                ),
                row=1,
                col=1
            )

            # EMA Linien
            fig.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data["EMA20"],
                    mode="lines",
                    name="EMA20"
                ),
                row=1,
                col=1
            )

            fig.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data["EMA50"],
                    mode="lines",
                    name="EMA50"
                ),
                row=1,
                col=1
            )

            # Buy Marker
            if not buy_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=buy_df["Date"],
                        y=buy_df["Price"],
                        mode="markers",
                        name="Buy Signal",
                        marker=dict(
                            symbol="triangle-up",
                            size=14,
                            color="green",
                            line=dict(width=1, color="darkgreen")
                        ),
                        hovertemplate="Buy<br>Datum: %{x}<br>Preis: %{y:.2f}<extra></extra>"
                    ),
                    row=1,
                    col=1
                )

             # Sell Marker
            if not sell_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=sell_df["Date"],
                        y=sell_df["Price"],
                        mode="markers",
                        name="Sell Signal",
                        marker=dict(
                            symbol="triangle-down",
                            size=14,
                            color="red",
                            line=dict(width=1, color="darkred")
                        ),
                        hovertemplate="Sell<br>Datum: %{x}<br>Preis: %{y:.2f}<extra></extra>"
                    ),
                    row=1,
                    col=1
                )

            # Fibonacci Linien
            for level_name, level_value in fib_levels.items():
                fig.add_hline(
                    y=level_value,
                    line_dash="dash",
                    annotation_text=f"Fib {level_name}",
                    annotation_position="right",
                    row=1,
                    col=1
                )

            # Support-Linien
            for support in supports:
                fig.add_hline(
                    y=support,
                    line_dash="dot",
                    annotation_text="Support",
                    annotation_position="left",
                    row=1,
                    col=1
                )

            # Resistance-Linien
            for resistance in resistances:
                fig.add_hline(
                    y=resistance,
                    line_dash="dot",
                    annotation_text="Resistance",
                    annotation_position="left",
                    row=1,
                    col=1
                )

            # Volumen (unten)
            fig.add_trace(
                go.Bar(
                    x=data.index,
                    y=data["Volume"],
                    name="Volumen"
                ),
                row=2,
                col=1
            )

            fig.update_layout(
                height=800,
                xaxis_rangeslider_visible=True,
                dragmode="zoom",
                hovermode="x unified"
            )

            st.plotly_chart(fig, use_container_width=True)

            st.write("### RSI")
            st.caption("RSI zeigt, ob ein Markt eher überkauft oder überverkauft ist.")
            st.line_chart(data[["RSI"]].dropna())

            st.write("### MACD")
            st.caption("MACD hilft bei der Einschätzung von Trend und Momentum.")
            st.line_chart(data[["MACD", "MACD_SIGNAL", "MACD_HIST"]].dropna())

            st.write("### Fibonacci-Level")
            fib_df = pd.DataFrame(
                {
                    "Level": list(fib_levels.keys()),
                    "Preis": list(fib_levels.values())
                }
            )
            st.dataframe(fib_df, use_container_width=True)

            st.write("### Support / Resistance")
            sr_df = pd.DataFrame(
                {
                    "Support": pd.Series(supports),
                    "Resistance": pd.Series(resistances)
                }
            )
            st.dataframe(sr_df, use_container_width=True)

            clean_data = data.dropna()

            if clean_data.empty:
                st.warning("Noch nicht genug Daten für die Analyse.")
            else:
                latest = clean_data.iloc[-1]

                close = latest["Close"]
                ema20 = latest["EMA20"]
                ema50 = latest["EMA50"]
                rsi = latest["RSI"]
                macd = latest["MACD"]
                macd_signal = latest["MACD_SIGNAL"]

                bullish_points = 0
                bearish_points = 0
                neutral_points = 0
                analysis_texts = []

                # 1. Trendbewertung
                if close > ema20 and ema20 > ema50:
                    bullish_points += 1
                    analysis_texts.append("Trend: bullish (Kurs über EMA20 und EMA50)")
                elif close < ema20 and ema20 < ema50:
                    bearish_points += 1
                    analysis_texts.append("Trend: bearish (Kurs unter EMA20 und EMA50)")
                else:
                    neutral_points += 1
                    analysis_texts.append("Trend: neutral / seitwärts")

                # 2. Kurs vs EMA20
                if close > ema20:
                    bullish_points += 1
                    analysis_texts.append("Kurzfristig positiv: Kurs über EMA20")
                elif close < ema20:
                    bearish_points += 1
                    analysis_texts.append("Kurzfristig schwächer: Kurs unter EMA20")
                else:
                    neutral_points += 1
                    analysis_texts.append("Kurs genau auf EMA20")

                # 3. RSI
                if rsi > 70:
                    bearish_points += 1
                    analysis_texts.append(f"RSI {rsi:.2f}: eher überkauft")
                elif rsi < 30:
                    bullish_points += 1
                    analysis_texts.append(f"RSI {rsi:.2f}: eher überverkauft, mögliche Erholung")
                else:
                    neutral_points += 1
                    analysis_texts.append(f"RSI {rsi:.2f}: neutral")

                # 4. MACD
                if macd > macd_signal:
                    bullish_points += 1
                    analysis_texts.append("MACD positiv: über der Signal-Linie")
                elif macd < macd_signal:
                    bearish_points += 1
                    analysis_texts.append("MACD negativ: unter der Signal-Linie")
                else:
                    neutral_points += 1
                    analysis_texts.append("MACD neutral")

                # 5. Nähe zu Fibonacci-Level
                nearest_fib_name = None
                nearest_fib_value = None
                nearest_fib_distance = None

                for level_name, level_value in fib_levels.items():
                    distance = abs(close - level_value)
                    if nearest_fib_distance is None or distance < nearest_fib_distance:
                        nearest_fib_distance = distance
                        nearest_fib_name = level_name
                        nearest_fib_value = level_value

                analysis_texts.append(
                    f"Nächstes Fibonacci-Level: {nearest_fib_name} bei {nearest_fib_value:.2f}"
                )

                st.write("### 🧠 Gesamtbewertung")

                if bullish_points > bearish_points:
                    st.success(
                        f"Gesamtbild eher bullish ({bullish_points} positiv / {bearish_points} negativ / {neutral_points} neutral)"
                    )
                elif bearish_points > bullish_points:
                    st.error(
                        f"Gesamtbild eher bearish ({bullish_points} positiv / {bearish_points} negativ / {neutral_points} neutral)"
                    )
                else:
                    st.warning(
                        f"Gesamtbild gemischt / neutral ({bullish_points} positiv / {bearish_points} negativ / {neutral_points} neutral)"
                    )

                for text in analysis_texts:
                    st.write("- " + text)

                st.write("### Detailwerte")

                m1, m2, m3, m4 = st.columns(4)
                m5, m6, m7, m8 = st.columns(4)

                with m1:
                    st.metric("Kurs", f"{close:.2f}")
                with m2:
                    st.metric("EMA20", f"{ema20:.2f}")
                with m3:
                    st.metric("EMA50", f"{ema50:.2f}")
                with m4:
                    st.metric("RSI", f"{rsi:.2f}")

                with m5:
                    st.metric("MACD", f"{macd:.2f}")
                with m6:
                    st.metric("MACD Signal", f"{macd_signal:.2f}")
                with m7:
                    st.metric("Swing High", f"{swing_high:.2f}")
                with m8:
                    st.metric("Swing Low", f"{swing_low:.2f}")

                st.caption(f"Intervall: {interval} | Zeitraum: {period}")

                col_summary, col_signals = st.columns([1.2, 1])

                with col_summary:
                    st.write("### 📝 Zusammenfassung")

                    summary = []

                    if bullish_points > bearish_points:
                        summary.append("Der Markt zeigt aktuell ein eher positives Gesamtbild.")
                    elif bearish_points > bullish_points:
                        summary.append("Der Markt wirkt derzeit eher schwach und tendenziell negativ.")
                    else:
                        summary.append("Der Markt zeigt aktuell kein klares Gesamtbild.")

                    if close > ema20 and close > ema50:
                        summary.append("Der Kurs liegt über den wichtigen gleitenden Durchschnitten, was auf einen stabilen Aufwärtstrend hindeutet.")
                    elif close < ema20 and close < ema50:
                        summary.append("Der Kurs liegt unter den gleitenden Durchschnitten, was auf einen Abwärtstrend hindeutet.")
                    else:
                        summary.append("Der Kurs bewegt sich um die gleitenden Durchschnitte, was auf Unsicherheit hindeutet.")

                    if rsi > 70:
                        summary.append("Der RSI befindet sich im überkauften Bereich, eine Korrektur wäre möglich.")
                    elif rsi < 30:
                        summary.append("Der RSI ist im überverkauften Bereich, eine Gegenbewegung nach oben könnte folgen.")
                    else:
                        summary.append("Der RSI ist im neutralen Bereich und zeigt kein extremes Signal.")

                    if macd > macd_signal:
                        summary.append("Der MACD ist positiv, was kurzfristig für weiteres Momentum sprechen kann.")
                    elif macd < macd_signal:
                        summary.append("Der MACD ist negativ, was auf schwächeres Momentum hindeutet.")
                    else:
                        summary.append("Der MACD zeigt aktuell kein klares Signal.")

                    summary.append(
                        f"Der Kurs befindet sich in der Nähe des Fibonacci-Levels {nearest_fib_name}, was eine mögliche Reaktionszone darstellt."
                    )

                    if supports:
                        summary.append(f"Wichtige Unterstützungen liegen in der Nähe von {round(supports[-1], 2)}.")
                    if resistances:
                        summary.append(f"Mögliche Widerstände liegen bei etwa {round(resistances[-1], 2)}.")

                    for sentence in summary:
                        st.write("- " + sentence)

                with col_signals:
                    st.write("### 🚨 Signale")

                    signals = []

                    if len(clean_data) >= 2:
                        prev = clean_data.iloc[-2]
                        curr = clean_data.iloc[-1]

                        # EMA Cross
                        if prev["EMA20"] <= prev["EMA50"] and curr["EMA20"] > curr["EMA50"]:
                            signals.append(("success", "Bullishes EMA-Cross: EMA20 hat EMA50 nach oben gekreuzt."))
                        elif prev["EMA20"] >= prev["EMA50"] and curr["EMA20"] < curr["EMA50"]:
                            signals.append(("error", "Bearishes EMA-Cross: EMA20 hat EMA50 nach unten gekreuzt."))

                        # MACD Cross
                        if prev["MACD"] <= prev["MACD_SIGNAL"] and curr["MACD"] > curr["MACD_SIGNAL"]:
                            signals.append(("success", "Bullishes MACD-Cross: MACD liegt jetzt über der Signal-Linie."))
                        elif prev["MACD"] >= prev["MACD_SIGNAL"] and curr["MACD"] < curr["MACD_SIGNAL"]:
                            signals.append(("error", "Bearishes MACD-Cross: MACD liegt jetzt unter der Signal-Linie."))

                        # RSI Warnungen
                        if curr["RSI"] > 70:
                            signals.append(("warning", f"RSI-Warnung: RSI liegt bei {curr['RSI']:.2f} und damit eher im überkauften Bereich."))
                        elif curr["RSI"] < 30:
                            signals.append(("warning", f"RSI-Warnung: RSI liegt bei {curr['RSI']:.2f} und damit eher im überverkauften Bereich."))

                    if not signals:
                        st.info("Aktuell keine frischen Signale erkannt.")
                    else:
                        for signal_type, message in signals:
                            if signal_type == "success":
                                st.success(message)
                            elif signal_type == "error":
                                st.error(message)
                            elif signal_type == "warning":
                                st.warning(message)
                            else:
                                st.info(message)

                    st.write("### 📊 Backtesting (EMA Strategie)")

                    if trades_df.empty:
                        st.info("Keine Trades im gewählten Zeitraum.")
                    else:
                        st.dataframe(trades_df, use_container_width=True)

                        total_return = ((equity_df["Equity"].iloc[-1] / 1000) - 1) * 100 if not equity_df.empty else 0
                        avg_return = trades_df["Trade Return After Fees %"].mean()
                        win_rate = (trades_df["Trade Return After Fees %"] > 0).mean() * 100

                        st.write("### 📈 Ergebnisse")

                        st.caption(f"Berechnet mit {fee_percent:.2f}% Gebühr pro Kauf und Verkauf.")
                        
                        st.write("### 🆚 Buy & Hold Vergleich")

                        start_price = data["Close"].iloc[0]
                        end_price = data["Close"].iloc[-1]
                        buy_hold_return = ((end_price / start_price) - 1) * 100
                        buy_hold_df = data[["Close"]].copy()
                        buy_hold_df["BuyHold"] = (buy_hold_df["Close"] / buy_hold_df["Close"].iloc[0]) * 1000

                        b1, b2 = st.columns(2)

                        with b1:
                            st.metric("Buy & Hold Return", f"{buy_hold_return:.2f}%")

                        with b2:
                            st.metric("Strategie Return", f"{total_return:.2f}%")

                        if total_return > buy_hold_return:
                            st.success("Die EMA-Strategie war in diesem Zeitraum besser als Buy & Hold.")
                        elif total_return < buy_hold_return:
                            st.warning("Buy & Hold war in diesem Zeitraum besser als die EMA-Strategie.")
                        else:
                            st.info("Beide Ansätze waren in diesem Zeitraum gleich stark.")
                        
                        st.write("### 📊 Strategie vs. Buy & Hold")

                        if not equity_df.empty:
                            strategy_curve = equity_df.copy()
                            strategy_curve["Date"] = pd.to_datetime(strategy_curve["Date"])
                            strategy_curve = strategy_curve.set_index("Date")

                            compare_bt_fig = go.Figure()

                            compare_bt_fig.add_trace(
                                go.Scatter(
                                    x=strategy_curve.index,
                                    y=strategy_curve["Equity"],
                                    mode="lines",
                                    name="EMA Strategie"
                                )
                            )

                            compare_bt_fig.add_trace(
                                go.Scatter(
                                    x=buy_hold_df.index,
                                    y=buy_hold_df["BuyHold"],
                                    mode="lines",
                                    name="Buy & Hold"
                                )
                            )

                            compare_bt_fig.update_layout(
                                height=500,
                                xaxis_title="Datum",
                                yaxis_title="Kapital",
                                dragmode="zoom",
                                hovermode="x unified",
                                xaxis_rangeslider_visible=True
                            )

                            st.plotly_chart(compare_bt_fig, use_container_width=True)

                        c1, c2, c3, c4 = st.columns(4)

                        with c1:
                            st.metric("Trades", len(trades_df))

                        with c2:
                            st.metric("Ø Return %", f"{avg_return:.2f}%")

                        with c3:
                            st.metric("Win Rate", f"{win_rate:.1f}%")

                        with c4:
                            st.metric("Strategie Return", f"{total_return:.2f}%")

                    st.write("### 🔔 Alarm-System")

                    alerts = []

                    if len(clean_data) >= 2:
                        prev = clean_data.iloc[-2]
                        curr = clean_data.iloc[-1]
                        current_price = curr["Close"]

                        # EMA Cross Alarm
                        if prev["EMA20"] <= prev["EMA50"] and curr["EMA20"] > curr["EMA50"]:
                            alerts.append(("success", "Alarm: Neues bullishes EMA-Cross erkannt."))
                        elif prev["EMA20"] >= prev["EMA50"] and curr["EMA20"] < curr["EMA50"]:
                            alerts.append(("error", "Alarm: Neues bearishes EMA-Cross erkannt."))

                        # MACD Cross Alarm
                        if prev["MACD"] <= prev["MACD_SIGNAL"] and curr["MACD"] > curr["MACD_SIGNAL"]:
                            alerts.append(("success", "Alarm: Neues bullishes MACD-Cross erkannt."))
                        elif prev["MACD"] >= prev["MACD_SIGNAL"] and curr["MACD"] < curr["MACD_SIGNAL"]:
                            alerts.append(("error", "Alarm: Neues bearishes MACD-Cross erkannt."))

                        # RSI Alarm
                        if curr["RSI"] > 70:
                            alerts.append(("warning", f"Alarm: RSI ist mit {curr['RSI']:.2f} im überkauften Bereich."))
                        elif curr["RSI"] < 30:
                            alerts.append(("warning", f"Alarm: RSI ist mit {curr['RSI']:.2f} im überverkauften Bereich."))

                        # Nähe zu Support
                        for support in supports:
                            if abs(current_price - support) / support < 0.01:
                                alerts.append(("info", f"Alarm: Kurs liegt nahe an Support bei {support:.2f}."))
                                break

                        # Nähe zu Resistance
                        for resistance in resistances:
                            if abs(current_price - resistance) / resistance < 0.01:
                                alerts.append(("info", f"Alarm: Kurs liegt nahe an Resistance bei {resistance:.2f}."))
                                break

                        # Nähe zu Fibonacci
                        if nearest_fib_value is not None:
                            if abs(current_price - nearest_fib_value) / nearest_fib_value < 0.01:
                                alerts.append(("info", f"Alarm: Kurs liegt nahe am Fibonacci-Level {nearest_fib_name} bei {nearest_fib_value:.2f}."))

                    if not alerts:
                        st.success("Aktuell keine kritischen Alarme.")
                    else:
                        for alert_type, message in alerts:
                            if alert_type == "success":
                                st.success(message)
                            elif alert_type == "error":
                                st.error(message)
                            elif alert_type == "warning":
                                st.warning(message)
                            else:
                                st.info(message)

        with tab_vergleich:
            st.write("### 📋 Aktienvergleich")
            st.caption("Technischer Schnellvergleich mehrerer Symbole auf Basis von EMA, RSI und MACD.")

            symbols = [s.strip().upper() for s in compare_input.split(",") if s.strip()]
            comparison_rows = []

            for symbol in symbols:
                try:
                    compare_data = load_data(symbol, period, interval)

                    if compare_data.empty:
                        comparison_rows.append({
                            "Symbol": symbol,
                            "Status": "Keine Daten"
                        })
                        continue

                    compare_data = compare_data.dropna(subset=["Close"])

                    if len(compare_data) < 30:
                        comparison_rows.append({
                            "Symbol": symbol,
                            "Status": "Zu wenig Daten"
                        })
                        continue

                    compare_data = calculate_indicators(compare_data)
                    compare_clean = compare_data.dropna()

                    if compare_clean.empty:
                        comparison_rows.append({
                            "Symbol": symbol,
                            "Status": "Keine Analyse möglich"
                        })
                        continue

                    latest_compare = compare_clean.iloc[-1]

                    close_c = latest_compare["Close"]
                    ema20_c = latest_compare["EMA20"]
                    ema50_c = latest_compare["EMA50"]
                    rsi_c = latest_compare["RSI"]
                    macd_c = latest_compare["MACD"]
                    macd_signal_c = latest_compare["MACD_SIGNAL"]

                    bullish = 0
                    bearish = 0
                    neutral = 0

                    if close_c > ema20_c and ema20_c > ema50_c:
                        bullish += 1
                        trend_text = "Bullish"
                    elif close_c < ema20_c and ema20_c < ema50_c:
                        bearish += 1
                        trend_text = "Bearish"
                    else:
                        neutral += 1
                        trend_text = "Neutral"

                    if close_c > ema20_c:
                        bullish += 1
                    elif close_c < ema20_c:
                        bearish += 1
                    else:
                        neutral += 1

                    if rsi_c > 70:
                        bearish += 1
                        rsi_text = "Überkauft"
                    elif rsi_c < 30:
                        bullish += 1
                        rsi_text = "Überverkauft"
                    else:
                        neutral += 1
                        rsi_text = "Neutral"

                    if macd_c > macd_signal_c:
                        bullish += 1
                        macd_text = "Positiv"
                    elif macd_c < macd_signal_c:
                        bearish += 1
                        macd_text = "Negativ"
                    else:
                        neutral += 1
                        macd_text = "Neutral"

                    if bullish > bearish:
                        overall = "Eher Bullish"
                    elif bearish > bullish:
                        overall = "Eher Bearish"
                    else:
                        overall = "Gemischt"

                    score = bullish - bearish

                    comparison_rows.append({
                        "Symbol": symbol,
                        "Kurs": round(float(close_c), 2),
                        "Trend": trend_text,
                        "RSI": round(float(rsi_c), 2),
                        "RSI Status": rsi_text,
                        "MACD": macd_text,
                        "Bullish Punkte": bullish,
                        "Bearish Punkte": bearish,
                        "Score": score,
                        "Gesamt": overall
                    })

                except Exception as e:
                    comparison_rows.append({
                        "Symbol": symbol,
                        "Status": f"Fehler: {str(e)}"
                    })

            comparison_df = pd.DataFrame(comparison_rows)

            if "Score" in comparison_df.columns:
                comparison_df = comparison_df.sort_values(by="Score", ascending=False).reset_index(drop=True)

            st.dataframe(comparison_df, use_container_width=True)
            if not comparison_df.empty and "Score" in comparison_df.columns:
                st.bar_chart(comparison_df.set_index("Symbol")["Score"])

            if not comparison_df.empty and "Score" in comparison_df.columns:
                best_row = comparison_df.iloc[0]
                worst_row = comparison_df.iloc[-1]

                st.write("### 🏆 Ranking-Info")
                st.success(f"Stärkstes Setup aktuell: {best_row['Symbol']} (Score: {best_row['Score']})")
                st.warning(f"Schwächstes Setup aktuell: {worst_row['Symbol']} (Score: {worst_row['Score']})")

            if not comparison_df.empty:
                csv_data = comparison_df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    label="📥 Vergleichstabelle als CSV herunterladen",
                    data=csv_data,
                    file_name=f"aktienvergleich_{period}_{interval}.csv",
                    mime="text/csv"
                )

            st.write("### 📈 Vergleichs-Chart (normalisiert, Plotly)")

            compare_chart_df = pd.DataFrame()

            for symbol in symbols:
                try:
                    chart_data = load_data(symbol, period, interval)

                    if chart_data.empty:
                        continue

                    if "Close" not in chart_data.columns:
                        continue

                    chart_data["Close"] = pd.to_numeric(chart_data["Close"], errors="coerce")
                    chart_data = chart_data.dropna(subset=["Close"])

                    if chart_data.empty:
                        continue

                    base_value = chart_data["Close"].iloc[0]
                    if base_value == 0:
                        continue

                    normalized = (chart_data["Close"] / base_value) * 100
                    compare_chart_df[symbol] = normalized

                except Exception:
                    continue

            if compare_chart_df.empty:
                st.info("Kein Vergleichs-Chart möglich.")
            else:
                compare_fig = go.Figure()

                for symbol in compare_chart_df.columns:
                    compare_fig.add_trace(
                        go.Scatter(
                            x=compare_chart_df.index,
                            y=compare_chart_df[symbol],
                            mode="lines",
                            name=symbol
                        )
                    )

                compare_fig.update_layout(
                    height=500,
                    xaxis_title="Datum",
                    yaxis_title="Performance (Start = 100)",
                    dragmode="zoom",
                    hovermode="x unified",
                    xaxis_rangeslider_visible=True
                )

                st.plotly_chart(compare_fig, use_container_width=True)