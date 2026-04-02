import pandas as pd


def backtest_ema_strategy(
    data: pd.DataFrame,
    initial_cash: float = 10000.0,
    fee_percent: float = 0.1,
    stop_loss_percent: float | None = None,
    take_profit_percent: float | None = None,
    use_rsi_filter: bool = False,
    rsi_min: float = 30.0,
    rsi_max: float = 70.0,
    use_ema200_filter: bool = False,
):
    """
    EMA20 / EMA50 Strategie mit optionalen Filtern:
    - Buy: EMA20 kreuzt über EMA50
    - Sell: EMA20 kreuzt unter EMA50
    - Optional: RSI Filter
    - Optional: EMA200 Filter
    - Optional: Stop Loss / Take Profit

    Returns:
    - trades_df
    - equity_df
    - buy_df
    - sell_df
    """

    if data is None or data.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty

    df = data.copy().reset_index().rename(columns={"index": "Date"})

    required_cols = ["Close", "EMA20", "EMA50"]
    for col in required_cols:
        if col not in df.columns:
            empty = pd.DataFrame()
            return empty, empty, empty, empty

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
        date_value = row["Date"]

        ema20 = row["EMA20"]
        ema50 = row["EMA50"]
        prev_ema20 = prev["EMA20"]
        prev_ema50 = prev["EMA50"]

        if pd.isna(ema20) or pd.isna(ema50) or pd.isna(prev_ema20) or pd.isna(prev_ema50):
            equity = cash + (position * price)
            equity_curve.append({"Date": date_value, "Equity": equity})
            continue

        rsi_ok = True
        if use_rsi_filter and "RSI" in df.columns:
            rsi_value = row["RSI"]
            if pd.isna(rsi_value):
                rsi_ok = False
            else:
                rsi_ok = float(rsi_value) >= float(rsi_min) and float(rsi_value) <= float(rsi_max)

        ema200_ok = True
        if use_ema200_filter and "EMA200" in df.columns:
            ema200_value = row["EMA200"]
            if pd.isna(ema200_value):
                ema200_ok = False
            else:
                ema200_ok = price > float(ema200_value)

        buy_signal = (
            position == 0
            and prev_ema20 < prev_ema50
            and ema20 > ema50
            and rsi_ok
            and ema200_ok
        )

        if buy_signal:
            quantity = cash / price if price > 0 else 0.0
            cost = quantity * price
            fee = cost * (float(fee_percent) / 100.0)
            total_cost = cost + fee

            if total_cost <= cash and quantity > 0:
                cash -= total_cost
                position = quantity
                entry_price = price
                entry_date = date_value

                trades.append({
                    "Date": date_value,
                    "Type": "BUY",
                    "Price": round(price, 4),
                    "Quantity": round(quantity, 6),
                    "Fee": round(fee, 4),
                    "Reason": "EMA Cross Up"
                })

                buy_points.append({
                    "Date": date_value,
                    "Price": round(price, 4)
                })

        elif position > 0:
            sell_reason = None

            if prev_ema20 > prev_ema50 and ema20 < ema50:
                sell_reason = "EMA Cross Down"

            if stop_loss_percent is not None and entry_price > 0:
                stop_price = entry_price * (1 - float(stop_loss_percent) / 100.0)
                if price <= stop_price:
                    sell_reason = "Stop Loss"

            if take_profit_percent is not None and entry_price > 0:
                tp_price = entry_price * (1 + float(take_profit_percent) / 100.0)
                if price >= tp_price:
                    sell_reason = "Take Profit"

            if sell_reason:
                revenue = position * price
                fee = revenue * (float(fee_percent) / 100.0)
                net_revenue = revenue - fee
                cash += net_revenue

                pnl = (price - entry_price) * position - fee

                trades.append({
                    "Date": date_value,
                    "Type": "SELL",
                    "Price": round(price, 4),
                    "Quantity": round(position, 6),
                    "Fee": round(fee, 4),
                    "PnL": round(pnl, 4),
                    "Reason": sell_reason,
                    "Entry Date": entry_date,
                })

                sell_points.append({
                    "Date": date_value,
                    "Price": round(price, 4)
                })

                position = 0.0
                entry_price = 0.0
                entry_date = None

        equity = cash + (position * price)
        equity_curve.append({
            "Date": date_value,
            "Equity": round(equity, 4)
        })

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve)
    buy_df = pd.DataFrame(buy_points)
    sell_df = pd.DataFrame(sell_points)

    return trades_df, equity_df, buy_df, sell_df
