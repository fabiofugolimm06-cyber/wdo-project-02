"""
microstructure/reporting/performance.py — relatório consolidado de performance.
"""

from __future__ import annotations

from typing import Any

import numpy as np

_REPORT_KEYS = (
    "total_return",
    "annualized_return",
    "sharpe",
    "max_drawdown",
    "calmar_ratio",
    "win_rate",
    "num_trades",
    "avg_trade_return",
    "profit_factor",
)

_BARS_PER_YEAR = 252


def _profit_factor(trades: list[dict]) -> float:
    """Soma ganhos / |soma perdas| a partir de ``trade_return``."""
    returns = [float(t["trade_return"]) for t in trades]
    gains = sum(r for r in returns if r > 0)
    losses = sum(r for r in returns if r < 0)
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / abs(losses))


def _annualized_return(total_return: float, n_bars: int) -> float:
    if n_bars < 2:
        return 0.0
    years = n_bars / _BARS_PER_YEAR
    if years <= 0:
        return 0.0
    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def _calmar_ratio(annualized_return: float, max_drawdown: float) -> float:
    dd = abs(max_drawdown)
    if dd < 1e-12:
        return 0.0
    return float(annualized_return / dd)


def generate_performance_report(backtest_result: dict[str, Any]) -> dict[str, float]:
    """
    Consolida métricas a partir do resultado de ``run_backtest_v3()``.

    Parameters
    ----------
    backtest_result : dict com chaves ``df``, ``trades``, ``metrics`` (saída v3).

    Returns
    -------
    dict padronizado com métricas de performance (9 campos).
    """
    if not isinstance(backtest_result, dict):
        raise TypeError("generate_performance_report: esperado dict de backtest v3.")

    metrics = backtest_result.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(
            "generate_performance_report: chave 'metrics' ausente ou inválida."
        )

    bt_df = backtest_result.get("df")
    trades = backtest_result.get("trades", [])
    if not isinstance(trades, list):
        raise ValueError("generate_performance_report: chave 'trades' deve ser lista.")

    n_bars = len(bt_df) if bt_df is not None else 0

    total_return = float(metrics.get("total_return", 0.0))
    sharpe = float(metrics.get("sharpe", 0.0))
    max_drawdown = float(metrics.get("max_drawdown", 0.0))
    win_rate = float(metrics.get("win_rate", 0.0))
    avg_trade_return = float(metrics.get("avg_trade_return", 0.0))

    num_trades = int(
        metrics.get(
            "completed_trades",
            metrics.get("num_trades", len(trades)),
        )
    )

    annualized_return = _annualized_return(total_return, n_bars)
    calmar_ratio = _calmar_ratio(annualized_return, max_drawdown)
    profit_factor = _profit_factor(trades)

    report = {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "calmar_ratio": calmar_ratio,
        "win_rate": win_rate,
        "num_trades": num_trades,
        "avg_trade_return": avg_trade_return,
        "profit_factor": profit_factor,
    }

    if set(report.keys()) != set(_REPORT_KEYS):
        raise RuntimeError("generate_performance_report: chaves internas inconsistentes.")

    return report
