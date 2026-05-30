"""
microstructure/risk/risk_engine.py — gerenciamento de risco (v1).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

_VALID_SIGNALS = {-1, 0, 1}


def calculate_position_size(
    capital: float,
    risk_per_trade: float,
    stop_loss_pct: float,
) -> dict[str, float]:
    """
    Tamanho de posição com base em risco por trade e stop percentual.

    ``risk_amount = capital * risk_per_trade``
    ``position_size = risk_amount / (capital * stop_loss_pct)``
    (equivale a ``risk_per_trade / stop_loss_pct`` em unidades relativas para Execution v1).

    Returns
    -------
    {"position_size": float}
    """
    if capital <= 0:
        raise ValueError(
            f"calculate_position_size: capital deve ser > 0, got {capital}."
        )
    if not 0.0 < risk_per_trade <= 1.0:
        raise ValueError(
            f"calculate_position_size: risk_per_trade deve estar em (0, 1], "
            f"got {risk_per_trade}."
        )
    if stop_loss_pct <= 0:
        raise ValueError(
            f"calculate_position_size: stop_loss_pct deve ser > 0, got {stop_loss_pct}."
        )

    risk_amount = capital * risk_per_trade
    denominator = capital * stop_loss_pct
    position_size = risk_amount / denominator

    return {"position_size": float(position_size)}


def check_daily_loss_limit(
    current_pnl: float,
    daily_loss_limit: float,
) -> dict[str, bool]:
    """
    Verifica limite de perda diária.

    ``daily_loss_limit`` é o piso de PnL (ex.: ``-150.0`` reais).
    ``risk_allowed`` é True se ``current_pnl >= daily_loss_limit``.

    Returns
    -------
    {"risk_allowed": bool}
    """
    if daily_loss_limit > 0:
        raise ValueError(
            "check_daily_loss_limit: daily_loss_limit deve ser <= 0 "
            f"(piso de perda), got {daily_loss_limit}."
        )

    return {"risk_allowed": bool(current_pnl >= daily_loss_limit)}


def check_max_drawdown(
    current_drawdown: float,
    max_drawdown_limit: float,
) -> dict[str, bool]:
    """
    Verifica drawdown máximo (frações negativas).

    Ex.: ``current_drawdown=-0.03``, ``max_drawdown_limit=-0.10`` → permitido.
    ``risk_allowed`` se ``current_drawdown >= max_drawdown_limit``.

    Returns
    -------
    {"risk_allowed": bool}
    """
    if max_drawdown_limit > 0:
        raise ValueError(
            "check_max_drawdown: max_drawdown_limit deve ser <= 0 "
            f"(ex.: -0.10), got {max_drawdown_limit}."
        )
    if current_drawdown > 0:
        raise ValueError(
            f"check_max_drawdown: current_drawdown deve ser <= 0, got {current_drawdown}."
        )

    return {"risk_allowed": bool(current_drawdown >= max_drawdown_limit)}


def risk_filter(
    signals: pd.Series | np.ndarray | list[int],
    allow_trading: bool = True,
) -> dict[str, Any]:
    """
    Aplica filtro de risco aos sinais (compatível com Execution v1).

    Se ``allow_trading`` é False, sinais não nulos viram 0 (flat).

    Returns
    -------
    dict com ``signals``, ``trading_enabled``, ``risk_allowed``.
    """
    if isinstance(signals, pd.Series):
        if len(signals) == 0:
            raise ValueError("risk_filter: signals vazio.")
        index = signals.index
        sig = signals.to_numpy(dtype=np.float64, copy=False)
        out_series = True
    else:
        sig = np.asarray(signals, dtype=np.float64)
        if sig.size == 0:
            raise ValueError("risk_filter: signals vazio.")
        index = pd.RangeIndex(len(sig))
        out_series = False

    sig_int = np.round(sig).astype(int)
    unique = set(np.unique(sig_int))
    if not unique.issubset(_VALID_SIGNALS):
        raise ValueError(
            f"risk_filter: sinais devem ser -1, 0 ou 1, got {sorted(unique)}."
        )

    trading_enabled = bool(allow_trading)
    risk_allowed = bool(allow_trading)

    if not allow_trading:
        sig_int = np.zeros_like(sig_int)

    if out_series:
        filtered = pd.Series(sig_int, index=index, name="signal")
    else:
        filtered = sig_int

    return {
        "signals": filtered,
        "trading_enabled": trading_enabled,
        "risk_allowed": risk_allowed,
    }
