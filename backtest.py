import pandas as pd


def backtest_ema_strategy(
    data: pd.DataFrame,
    initial_cash: float = 10000.0,
    fee_percent: float = 0.1,
    stop_loss_percent=None,
    take_profit_percent=None,
    use_rsi_filter: bool = False,
    rsi_min: float = 30.0,
    rsi_max: float = 70.0,
    use_ema200_filter: bool = False,
    *args,
    **kwargs
):
    """
    Robuste EMA20/EMA50 Backtest-Funktion für Emanacci.
    Akzeptiert zusätzliche unbekannte Parameter über **kwargs, damit
    App-Aufrufe nicht wegen neuer/alter Parameter crashen.
    Gibt immer 4 DataFrames zurück:
    - trades_df
    - equity_df
    - buy_df
    - sell_df
    """

    if data is None or len(data) == 0:
        empty = pd.DataFrame()
        return empty, empty, empty, empty

    df = data.copy()

    if not isinstance(df, pd.DataFrame):
        empty = pd.DataFrame()
        return empty, empty, empty, empty

    if "Close" not in df.columns or "EMA20" not in df.columns or "EMA50" not in df.columns:
        empty = pd.DataFrame()
        return empty, empty, empty, empty

    df = df.copy().reset_index()
    date_col = df.columns[0]

    cash = float(initial_cash)
    position = 0.0
    entry_price = 0.0
    entry_date = None

    trades = []
    equity_curve = []
    buy_points = []
    sell_points = []

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]

        price = float(row["Close"])
        dt = row[date_col]

        ema20 = row["EMA20"]
        ema50 = row["EMA50"]
        prev_ema20 = prev["EMA20"]
        prev_ema50 = prev["EMA50"]

        if pd.isna(ema20) or pd.isna(ema50) or pd.isna(prev_ema20) or pd.isna(prev_ema50):
            equity_curve.append({"Date": dt, "Equity": cash + position * price})
            continue

        rsi_ok = True
        if use_rsi_filter:
            if "RSI" not in df.columns or pd.isna(row.get("RSI")):
                rsi_ok = False
            else:
                rsi_val = float(row["RSI"])
                rsi_ok = float(rsi_min) <= rsi_val <= float(rsi_max)

        ema200_ok = True
        if use_ema200_filter:
            if "EMA200" not in df.columns or pd.isna(row.get("EMA200")):
                ema200_ok = False
            else:
                ema200_ok = price > float(row["EMA200"])

        buy_signal = (
            position == 0
            and prev_ema20 < prev_ema50
            and ema20 > ema50
            and rsi_ok
            and ema200_ok
        )

        if buy_signal:
            qty = cash / price if price > 0 else 0.0
            gross_cost = qty * price
            fee = gross_cost * (float(fee_percent) / 100.0)
            total_cost = gross_cost + fee

            if qty > 0 and total_cost <= cash:
                cash -= total_cost
                position = qty
                entry_price = price
                entry_date = dt

                trades.append({
                    "Date": dt,
                    "Type": "BUY",
                    "Price": round(price, 4),
                    "Quantity": round(qty, 6),
                    "Fee": round(fee, 4),
                    "Reason": "EMA Cross Up"
                })
                buy_points.append({"Date": dt, "Price": round(price, 4)})

        elif position > 0:
            sell_reason = None

            if prev_ema20 > prev_ema50 and ema20 < ema50:
                sell_reason = "EMA Cross Down"

            if stop_loss_percent is not None and entry_price > 0:
                stop_level = entry_price * (1 - float(stop_loss_percent) / 100.0)
                if price <= stop_level:
                    sell_reason = "Stop Loss"

            if take_profit_percent is not None and entry_price > 0:
                tp_level = entry_price * (1 + float(take_profit_percent) / 100.0)
                if price >= tp_level:
                    sell_reason = "Take Profit"

            if sell_reason:
                gross_rev = position * price
                fee = gross_rev * (float(fee_percent) / 100.0)
                net_rev = gross_rev - fee
                pnl = (price - entry_price) * position - fee

                cash += net_rev

                trades.append({
                    "Date": dt,
                    "Type": "SELL",
                    "Price": round(price, 4),
                    "Quantity": round(position, 6),
                    "Fee": round(fee, 4),
                    "PnL": round(pnl, 4),
                    "Reason": sell_reason,
                    "Entry Date": entry_date,
                })
                sell_points.append({"Date": dt, "Price": round(price, 4)})

                position = 0.0
                entry_price = 0.0
                entry_date = None

        equity_curve.append({
            "Date": dt,
            "Equity": round(cash + position * price, 4)
        })

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve)
    buy_df = pd.DataFrame(buy_points)
    sell_df = pd.DataFrame(sell_points)

    return trades_df, equity_df, buy_df, sell_df
