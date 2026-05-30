"""
microstructure/backtest/engine_v2.py
-------------------------------------
Backtest com custos de transação e slippage (baseline = engine_v1).

Custos aplicados somente quando a posição muda (trade_event).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def run_backtest_v2(
    df: pd.DataFrame,
    signals: pd.Series,
    price_col: str = "close",
    cost_per_trade: float = 0.0001,
    slippage: float = 0.00005,
) -> dict:
    """
    Backtest v2 — igual ao v1 com custos por mudança de posição.

    Parameters
    ----------
    df : DataFrame OHLCV alinhado aos sinais.
    signals : Series de sinais (-1, 0, 1).
    price_col : coluna de preço para retorno futuro.
    cost_per_trade : custo fixo por evento de trade (fração).
    slippage : slippage por evento de trade (fração).

    Returns
    -------
    dict com ``df`` (colunas extras: trade_event, cost, gross_return)
    e ``metrics`` (mesmas chaves do v1).
    """
    df = df.copy()

    # future returns (sem lookahead bias)
    df["future_return"] = df[price_col].pct_change().shift(-1)

    # signals
    df["signal"] = signals

    # position
    df["position"] = df["signal"].replace(0, np.nan).ffill().fillna(0)

    # detectar mudança de posição
    df["trade_event"] = df["position"].diff().abs().fillna(0)

    # retorno bruto
    df["gross_return"] = df["position"] * df["future_return"]

    # custo apenas quando houver trade
    cost_rate = cost_per_trade + slippage
    df["cost"] = df["trade_event"] * cost_rate

    # strategy return líquido
    df["strategy_return"] = df["gross_return"] - df["cost"]

    # equity curve
    df["equity"] = (1 + df["strategy_return"]).cumprod()

    # drawdown
    df["peak"] = df["equity"].cummax()
    df["drawdown"] = df["equity"] / df["peak"] - 1

    # metrics (mesmas chaves do v1)
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
            "num_trades": len(trades),
            "cost_per_trade": cost_per_trade,
            "slippage": slippage,
            "total_cost_paid": float(df["cost"].sum()),
            "num_trade_events": int((df["trade_event"] > 0).sum()),
        },
    }
