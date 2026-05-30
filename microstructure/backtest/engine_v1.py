import numpy as np
import pandas as pd


def run_backtest(df, signals, price_col="close"):

    df = df.copy()

    # future returns (sem lookahead bias)
    df["future_return"] = df[price_col].pct_change().shift(-1)

    # signals
    df["signal"] = signals

    # position
    df["position"] = df["signal"].replace(0, np.nan).ffill().fillna(0)

    # strategy return
    df["strategy_return"] = df["position"] * df["future_return"]

    # equity curve
    df["equity"] = (1 + df["strategy_return"]).cumprod()

    # drawdown
    df["peak"] = df["equity"].cummax()
    df["drawdown"] = df["equity"] / df["peak"] - 1

    # metrics
    total_return = df["equity"].iloc[-2] - 1

    sharpe = (
        df["strategy_return"].mean()
        / df["strategy_return"].std()
    ) * np.sqrt(252)

    max_dd = df["drawdown"].min()

    trades = df[df["signal"] != 0]
    win_rate = (trades["strategy_return"] > 0).mean()

    return {
        "df": df,
        "metrics": {
            "total_return": total_return,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "num_trades": len(trades)
        }
    }
