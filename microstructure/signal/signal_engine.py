"""
microstructure/signal/signal_engine.py
---------------------------------------
Transforma matriz de features (X) em sinais simples de trading.

Regras (determinísticas, vetorizadas):
    signal =  1  se  returns > 0  AND  delta > 0   (compra)
    signal = -1  se  returns < 0  AND  delta < 0   (venda)
    signal =  0  caso contrário                   (neutro)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_REQUIRED_COLS = ("returns", "delta")


def generate_signals(X: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona coluna ``signal`` ao DataFrame de features e retorna cópia.

    Parameters
    ----------
    X : DataFrame com colunas ``returns`` e ``delta`` (output de build_dataset).

    Returns
    -------
    pd.DataFrame — mesmo índice e colunas de X + ``signal`` (int8).

    Raises
    ------
    ValueError : colunas obrigatórias ausentes ou X vazio.
    """
    if X is None or len(X) == 0:
        raise ValueError("generate_signals: DataFrame vazio.")

    missing = [c for c in _REQUIRED_COLS if c not in X.columns]
    if missing:
        raise ValueError(
            f"generate_signals: colunas obrigatórias ausentes: {missing}. "
            f"Disponíveis: {list(X.columns)}"
        )

    out = X.copy()
    returns = out["returns"].to_numpy(dtype=np.float64, copy=False)
    delta   = out["delta"].to_numpy(dtype=np.float64, copy=False)

    buy_mask  = (returns > 0) & (delta > 0)
    sell_mask = (returns < 0) & (delta < 0)

    out["signal"] = np.select(
        [buy_mask, sell_mask],
        [np.int8(1), np.int8(-1)],
        default=np.int8(0),
    ).astype(np.int8)

    return out
