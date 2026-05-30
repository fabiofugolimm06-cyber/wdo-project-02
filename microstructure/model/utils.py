"""
microstructure/model/utils.py — limpeza de X para sklearn (sem alterar features).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def report_nan_features(X: pd.DataFrame) -> dict[str, int]:
    """Contagem de NaN por coluna (diagnóstico de warmup)."""
    counts = X.isna().sum()
    return {str(col): int(counts[col]) for col in counts.index if counts[col] > 0}


def drop_nan_feature_rows(
    X: pd.DataFrame,
    y: pd.Series,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Prepara ``X`` para sklearn sem remover barras além do labeling.

    Após ``drop_invalid_label_rows`` (horizon), a única redução de linhas deve
    ser o shift de labels. Warmup de features é imputado de forma causal
    (``ffill`` + ``0``), não por ``drop`` de linhas.
    """
    if len(X) != len(y):
        raise ValueError(
            f"drop_nan_feature_rows: len(X)={len(X)} != len(y)={len(y)}."
        )
    if not X.index.equals(y.index):
        raise ValueError("drop_nan_feature_rows: índices de X e y devem ser idênticos.")

    X_work = X.copy()
    y_work = y.copy()

    mask = y_work.notna()
    X_out = X_work.loc[mask].copy()
    y_out = y_work.loc[mask].copy()

    X_out = X_out.replace([np.inf, -np.inf], np.nan)
    X_out = X_out.ffill()
    X_out = X_out.fillna(0.0)

    if X_out.isna().any().any():
        bad = report_nan_features(X_out)
        raise ValueError(
            "drop_nan_feature_rows: NaN residual após imputação causal: "
            f"{bad}"
        )

    # Ordem temporal estável (determinismo entre runs)
    X_out = X_out.sort_index()
    y_out = y_out.sort_index()

    return X_out, y_out
