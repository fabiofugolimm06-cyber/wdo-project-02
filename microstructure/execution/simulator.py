"""
microstructure/execution/simulator.py — execução simulada (separada do backtest).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

_VALID_SIGNALS = {-1, 0, 1}


def simulate_execution(
    signals: pd.Series | np.ndarray | list[int],
    initial_capital: float = 100_000.0,
    position_size: float = 1.0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Simula execução de ordens a partir de sinais discretos.

    Regras de posição
    -----------------
    signal =  1 → posição comprada  (+position_size)
    signal = -1 → posição vendida   (-position_size)
    signal =  0 → flat (0)

    Colunas adicionadas
    -------------------
    current_position, position_changes, executed_orders, gross_exposure

    Parameters
    ----------
    signals : série de sinais {-1, 0, 1} (ex.: ``X['signal']``).
    initial_capital : capital base para exposição bruta.
    position_size : tamanho por unidade de sinal.

    Returns
    -------
    (execution_df, metrics)
    """
    if initial_capital <= 0:
        raise ValueError(
            f"simulate_execution: initial_capital deve ser > 0, got {initial_capital}."
        )
    if position_size <= 0:
        raise ValueError(
            f"simulate_execution: position_size deve ser > 0, got {position_size}."
        )

    if isinstance(signals, pd.Series):
        if len(signals) == 0:
            raise ValueError("simulate_execution: signals vazio.")
        index = signals.index
        sig = signals.to_numpy(dtype=np.float64, copy=False)
    else:
        sig = np.asarray(signals, dtype=np.float64)
        if sig.size == 0:
            raise ValueError("simulate_execution: signals vazio.")
        index = pd.RangeIndex(len(sig))

    sig_int = np.round(sig).astype(int)
    unique = set(np.unique(sig_int))
    if not unique.issubset(_VALID_SIGNALS):
        raise ValueError(
            f"simulate_execution: sinais devem ser -1, 0 ou 1, got {sorted(unique)}."
        )

    current_position = sig_int.astype(np.float64) * position_size
    position_changes = np.diff(current_position, prepend=0.0)
    executed_orders = (position_changes != 0).astype(np.int8)
    gross_exposure = np.abs(current_position) * initial_capital

    execution_df = pd.DataFrame(
        {
            "signal": sig_int,
            "current_position": current_position,
            "position_changes": position_changes,
            "executed_orders": executed_orders,
            "gross_exposure": gross_exposure,
        },
        index=index,
    )

    prev_position = np.concatenate(([0.0], current_position[:-1]))
    long_entries = int(
        np.sum((current_position > 0) & (prev_position <= 0))
    )
    short_entries = int(
        np.sum((current_position < 0) & (prev_position >= 0))
    )
    flat_periods = int(np.sum(current_position == 0))

    metrics = {
        "num_orders": int(executed_orders.sum()),
        "long_entries": long_entries,
        "short_entries": short_entries,
        "flat_periods": flat_periods,
    }

    return execution_df, metrics
