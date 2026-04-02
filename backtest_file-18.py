import pandas as pd

def backtest_ema_strategy(
    data: pd.DataFrame,
    initial_cash: float = 10000,
    fee_percent: float = 0.1,
    stop_loss_percent: float = None,
    take_profit_percent: float = None,
):
    cash = initial_cash
    position = 0.0
    entry_price = 0.0

    trades = []
    equity_curve = []

    for i in range(1, len(data)):
        row = data.iloc[i]
        prev = data.iloc[i - 1]

        price = float(row["Close"])

        ema20 = row.get("EMA20")
        ema50 = row.get("EMA50")

        prev_ema20 = prev.get("EMA20")
        prev_ema50 = prev.get("EMA50")

        if pd.isna(ema20) or pd.isna(ema50):
            continue

        if position == 0:
            if prev_ema20 < prev_ema50 and ema20 > ema50:
                quantity = cash / price
                cost = quantity * price
                fee = cost * (fee_percent / 100)

                cash -= (cost + fee)
                position = quantity
                entry_price = price

                trades.append({
                    "type": "BUY",
                    "price": price,
                    "date": row.name,
                    "quantity": quantity
                })

        else:
            sell_reason = None

            if prev_ema20 > prev_ema50 and ema20 < ema50:
                sell_reason = "EMA Cross"

            if stop_loss_percent:
                if price <= entry_price * (1 - stop_loss_percent / 100):
                    sell_reason = "Stop Loss"

            if take_profit_percent:
                if price >= entry_price * (1 + take_profit_percent / 100):
                    sell_reason = "Take Profit"

            if sell_reason:
                revenue = position * price
                fee = revenue * (fee_percent / 100)

                cash += (revenue - fee)

                trades.append({
                    "type": "SELL",
                    "price": price,
                    "date": row.name,
                    "quantity": position,
                    "reason": sell_reason
                })

                position = 0
                entry_price = 0

        equity = cash + (position * price)
        equity_curve.append(equity)

    return trades, equity_curve
