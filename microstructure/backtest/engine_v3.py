"""
microstructure/backtest/engine_v3.py
-------------------------------------
Backtest com holding period, stop loss, take profit e custos (herda v2).

Exit reasons: signal_flip | max_hold | stop_loss | take_profit
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EXIT_REASONS = frozenset({
    "signal_flip",
    "max_hold",
    "stop_loss",
    "take_profit",
})


def _signed_pnl_pct(price: float, entry: float, position: int) -> float:
    """Retorno percentual da posição (long=+1, short=-1)."""
    if position > 0:
        return price / entry - 1.0
    return entry / price - 1.0


def _build_position_v3(
    close: np.ndarray,
    signals: np.ndarray,
    max_hold_bars: int,
    stop_loss: float,
    take_profit: float,
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """
    Simulação bar-a-bar (causal): entradas por sinal, saídas por regras.

    Returns
    -------
    position, exit_reason (str/object per bar), completed_trades log
    """
    n = len(close)
    position = np.zeros(n, dtype=np.float64)
    exit_reason = np.full(n, None, dtype=object)

    current_pos = 0
    entry_price: float | None = None
    entry_bar: int = 0
    bars_held = 0

    trade_log: list[dict] = []

    for i in range(n):
        price = float(close[i])
        sig = int(signals[i])
        pos_start = current_pos

        if current_pos != 0 and entry_price is not None:
            bars_held += 1
            pnl_pct = _signed_pnl_pct(price, entry_price, current_pos)
            reason: str | None = None

            if pnl_pct <= -stop_loss:
                reason = "stop_loss"
            elif pnl_pct >= take_profit:
                reason = "take_profit"
            elif bars_held >= max_hold_bars:
                reason = "max_hold"
            elif sig != 0 and np.sign(sig) != current_pos:
                reason = "signal_flip"

            if reason is not None:
                exit_reason[i] = reason
                trade_log.append({
                    "entry_bar": entry_bar,
                    "exit_bar": i,
                    "holding_bars": bars_held,
                    "trade_return": pnl_pct,
                    "exit_reason": reason,
                    "position": current_pos,
                })
                current_pos = 0
                entry_price = None
                bars_held = 0

                if reason == "signal_flip" and sig != 0:
                    current_pos = int(np.sign(sig))
                    entry_price = price
                    entry_bar = i
                    bars_held = 0

        if current_pos == 0 and sig != 0:
            current_pos = int(np.sign(sig))
            entry_price = price
            entry_bar = i
            bars_held = 0

        position[i] = float(current_pos)

    return position, exit_reason, trade_log


def run_backtest_v3(
    df: pd.DataFrame,
    signals: pd.Series,
    price_col: str = "close",
    max_hold_bars: int = 5,
    stop_loss: float = 0.01,
    take_profit: float = 0.02,
    cost_per_trade: float = 0.0001,
    slippage: float = 0.00005,
) -> dict:
    """
    Backtest v3 — gestão de trade com SL/TP/holding + custos v2.

    Parameters
    ----------
    max_hold_bars : máximo de barras em posição antes de saída forçada.
    stop_loss : perda máxima relativa (ex.: 0.01 = 1%).
    take_profit : ganho alvo relativo (ex.: 0.02 = 2%).
    cost_per_trade, slippage : herdados do v2 (aplicados em trade_event).
    """
    df = df.copy()
    n = len(df)

    if n < 2:
        raise ValueError("run_backtest_v3: DataFrame precisa de pelo menos 2 barras.")

    close = df[price_col].to_numpy(dtype=float)
    sig = signals.reindex(df.index).fillna(0).to_numpy(dtype=float)

    df["future_return"] = df[price_col].pct_change().shift(-1)
    df["signal"] = sig

    position, exit_reason, trade_log = _build_position_v3(
        close, sig, max_hold_bars, stop_loss, take_profit
    )

    df["position"] = position
    df["exit_reason"] = exit_reason

    df["trade_event"] = df["position"].diff().abs().fillna(0)
    if position[0] != 0:
        df.loc[df.index[0], "trade_event"] = abs(position[0])

    cost_rate = cost_per_trade + slippage
    df["gross_return"] = df["position"] * df["future_return"]
    df["cost"] = df["trade_event"] * cost_rate
    df["strategy_return"] = df["gross_return"] - df["cost"]

    df["equity"] = (1 + df["strategy_return"]).cumprod()
    df["peak"] = df["equity"].cummax()
    df["drawdown"] = df["equity"] / df["peak"] - 1

    total_return = float(df["equity"].iloc[-2] - 1) if n >= 2 else 0.0

    strat = df["strategy_return"].dropna()
    sharpe = (
        float(strat.mean() / strat.std() * np.sqrt(252))
        if strat.std() > 0 and len(strat) > 1
        else 0.0
    )

    max_dd = float(df["drawdown"].min())

    signal_bars = df[df["signal"] != 0]
    win_rate = float((signal_bars["strategy_return"] > 0).mean()) if len(signal_bars) else 0.0

    completed = trade_log
    trade_returns = [t["trade_return"] for t in completed]
    holding_periods = [t["holding_bars"] for t in completed]

    avg_trade_return = float(np.mean(trade_returns)) if trade_returns else 0.0
    avg_holding_period = float(np.mean(holding_periods)) if holding_periods else 0.0

    stop_loss_hits = sum(1 for t in completed if t["exit_reason"] == "stop_loss")
    take_profit_hits = sum(1 for t in completed if t["exit_reason"] == "take_profit")

    exit_counts = {r: 0 for r in EXIT_REASONS}
    for t in completed:
        exit_counts[t["exit_reason"]] = exit_counts.get(t["exit_reason"], 0) + 1

    return {
        "df": df,
        "trades": completed,
        "metrics": {
            "total_return": total_return,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "num_trades": len(signal_bars),
            "cost_per_trade": cost_per_trade,
            "slippage": slippage,
            "total_cost_paid": float(df["cost"].sum()),
            "num_trade_events": int((df["trade_event"] > 0).sum()),
            "avg_trade_return": avg_trade_return,
            "avg_holding_period": avg_holding_period,
            "stop_loss_hits": stop_loss_hits,
            "take_profit_hits": take_profit_hits,
            "completed_trades": len(completed),
            "exit_signal_flip": exit_counts.get("signal_flip", 0),
            "exit_max_hold": exit_counts.get("max_hold", 0),
            "exit_stop_loss": stop_loss_hits,
            "exit_take_profit": take_profit_hits,
            "max_hold_bars": max_hold_bars,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        },
    }
