"""
microstructure/labeling/triple_barrier.py — Triple Barrier (skeleton v1).

Implementação completa prevista para v2 (López de Prado).
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

from microstructure.labeling.utils import validate_price_series

LabelTB = Literal[-1, 0, 1]


def create_triple_barrier_labels(
    df: pd.DataFrame,
    price_col: str = "fechamento",
    horizon: int = 5,
    upper_barrier: float = 0.02,
    lower_barrier: float = 0.01,
    vertical_barrier: int | None = None,
) -> pd.Series:
    """
    Triple Barrier labeling — estrutura inicial (não implementado em v1).

    Parâmetros planejados
    ---------------------
    upper_barrier : take-profit relativo (ex.: +2%).
    lower_barrier : stop-loss relativo (ex.: -1%).
    vertical_barrier : timeout em barras (default = ``horizon``).

    Retorno esperado (futuro)
    -------------------------
    Series com valores em {-1, 0, 1}:
        +1 = barreira superior atingida primeiro
        -1 = barreira inferior atingida primeiro
         0 = barreira vertical (tempo)

    Raises
    ------
    NotImplementedError : v1 expõe apenas contrato e validação de entrada.
    """
    if horizon < 1:
        raise ValueError(
            f"create_triple_barrier_labels: horizon deve ser >= 1, got {horizon}."
        )
    if upper_barrier <= 0 or lower_barrier <= 0:
        raise ValueError("Barreiras superior e inferior devem ser > 0.")

    validate_price_series(df, price_col)

    _ = vertical_barrier if vertical_barrier is not None else horizon

    raise NotImplementedError(
        "Triple Barrier labeling será implementado na v2. "
        "Use create_horizon_labels() para targets supervisionados em v1."
    )
