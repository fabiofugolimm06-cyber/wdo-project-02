"""
microstructure/labeling/utils.py — utilitários anti-leakage para labeling.
"""

from __future__ import annotations

import pandas as pd


def validate_price_series(
    df: pd.DataFrame,
    price_col: str = "fechamento",
) -> pd.Series:
    """
    Extrai série de preço e valida pré-condições do labeling.

    Raises
    ------
    ValueError : DataFrame vazio.
    TypeError : índice não é DatetimeIndex.
    ValueError : coluna de preço ausente.
    """
    if df is None or len(df) == 0:
        raise ValueError("labeling: DataFrame vazio.")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("labeling: índice deve ser DatetimeIndex.")

    if not df.index.is_monotonic_increasing:
        raise ValueError("labeling: índice deve ser monotônico crescente (sort_index).")

    if price_col not in df.columns:
        raise ValueError(
            f"labeling: coluna '{price_col}' ausente. "
            f"Disponíveis: {list(df.columns)}"
        )

    return df[price_col].astype(float)


def drop_invalid_label_rows(
    X: pd.DataFrame,
    y: pd.Series,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Remove barras onde ``y`` é NaN (sem horizonte futuro completo).

    Uso típico após ``create_horizon_labels`` para dataset ML limpo.
    """
    if len(X) != len(y):
        raise ValueError(
            f"labeling: len(X)={len(X)} != len(y)={len(y)} — realinhar índices."
        )
    if not X.index.equals(y.index):
        raise ValueError("labeling: índices de X e y devem ser idênticos.")

    mask = y.notna()
    return X.loc[mask].copy(), y.loc[mask].copy()
