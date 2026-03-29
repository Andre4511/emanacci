import pandas as pd
print("Backtest geladen")

def backtest_ema_strategy(
    data: pd.DataFrame,
    initial_capital: float = 1000,
    fee_percent: float = 0.1,
    stop_loss_percent: float = 5.0,
    take_profit_percent: float = 10.0,
    use_rsi_filter: bool = True,
    rsi_min: float = 40.0,
    rsi_max: float = 70.0,
    use_ema200_filter: bool = False
):
    data = data.copy()

    position = 0
    shares = 0.0
    entry_price = 0.0
    capital = initial_capital
    entry_capital_after_fee = 0.0
    entry_date = None

    trades = []
    equity_history = []
    buy_markers = []
    sell_markers = []

    fee_rate = fee_percent / 100
    stop_loss_rate = stop_loss_percent / 100
    take_profit_rate = take_profit_percent / 100

    for i in range(1, len(data)):
        prev = data.iloc[i - 1]
        curr = data.iloc[i]
        current_date = curr.name
        current_close = curr["Close"]
        current_rsi = curr["RSI"]

        buy_signal = prev["EMA20"] <= prev["EMA50"] and curr["EMA20"] > curr["EMA50"]

        rsi_ok = True
        if use_rsi_filter:
            rsi_ok = rsi_min <= current_rsi <= rsi_max

        ema200_ok = True
        if use_ema200_filter:
            ema200_ok = current_close > curr["EMA200"]

        if position == 0 and buy_signal and rsi_ok and ema200_ok:
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

        elif position == 1:
            exit_reason = None
            exit_price = current_close

            stop_loss_price = entry_price * (1 - stop_loss_rate)
            take_profit_price = entry_price * (1 + take_profit_rate)

            if stop_loss_percent > 0 and current_close <= stop_loss_price:
                exit_reason = "Stop-Loss"
            elif take_profit_percent > 0 and current_close >= take_profit_price:
                exit_reason = "Take-Profit"
            elif prev["EMA20"] >= prev["EMA50"] and curr["EMA20"] < curr["EMA50"]:
                exit_reason = "EMA Cross Down"

            if exit_reason is not None:
                exit_date = current_date

                gross_exit_value = shares * exit_price
                exit_fee = gross_exit_value * fee_rate
                capital = gross_exit_value - exit_fee

                trade_return_pct = ((exit_price - entry_price) / entry_price) * 100
                trade_return_after_fees_pct = (
                    ((capital / entry_capital_after_fee) - 1) * 100
                    if entry_capital_after_fee > 0 else 0
                )

                trades.append({
                    "Entry Date": entry_date,
                    "Exit Date": exit_date,
                    "Entry Price": round(entry_price, 2),
                    "Exit Price": round(exit_price, 2),
                    "Exit Reason": exit_reason,
                    "RSI at Entry": round(current_rsi, 2),
                    "Trade Return %": round(trade_return_pct, 2),
                    "Trade Return After Fees %": round(trade_return_after_fees_pct, 2),
                    "Capital After Trade": round(capital, 2)
                })

                sell_markers.append({
                    "Date": current_date,
                    "Price": current_close,
                    "Reason": exit_reason
                })

                position = 0
                shares = 0.0
                entry_capital_after_fee = 0.0
                entry_date = None

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