"""
microstructure/model/split.py — split temporal sem shuffle (anti-leakage).
"""

from __future__ import annotations

import pandas as pd


def train_test_split_time_series(
    X: pd.DataFrame,
    y: pd.Series,
    train_size: float = 0.70,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Divide ``X`` e ``y`` em treino e teste preservando ordem temporal.

    - Sem shuffle: treino = primeiras ``floor(n * train_size)`` barras;
      teste = restante.
    - Índices de ``X`` e ``y`` devem coincidir.

    Parameters
    ----------
    X, y : features e labels alinhados (ex.: após ``drop_invalid_label_rows``).
    train_size : fração em (0, 1) para treino.

    Returns
    -------
    X_train, X_test, y_train, y_test
    """
    if not 0.0 < train_size < 1.0:
        raise ValueError(
            f"train_test_split_time_series: train_size deve estar em (0, 1), got {train_size}."
        )

    if len(X) != len(y):
        raise ValueError(
            f"train_test_split_time_series: len(X)={len(X)} != len(y)={len(y)}."
        )

    if not X.index.equals(y.index):
        raise ValueError("train_test_split_time_series: índices de X e y devem ser idênticos.")

    n = len(X)
    split_idx = int(n * train_size)

    if split_idx < 1 or split_idx >= n:
        raise ValueError(
            f"train_test_split_time_series: split inválido n={n}, train_size={train_size} "
            f"→ split_idx={split_idx}. Aumente amostras ou ajuste train_size."
        )

    # Sem shuffle: partição estritamente temporal (primeiras barras = treino).
    X_work = X.copy()
    y_work = y.copy()

    X_train = X_work.iloc[:split_idx].copy()
    X_test = X_work.iloc[split_idx:].copy()
    y_train = y_work.iloc[:split_idx].copy()
    y_test = y_work.iloc[split_idx:].copy()

    return X_train, X_test, y_train, y_test
