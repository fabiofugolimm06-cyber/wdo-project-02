"""
microstructure/model/purged_kfold.py — Purged K-Fold (López de Prado, v1).
"""

from __future__ import annotations

from typing import Any, Iterator

import numpy as np
import pandas as pd

from microstructure.model.metrics import evaluate_classifier
from microstructure.model.trainer import train_logistic_model

_METRIC_KEYS = ("accuracy", "precision", "recall", "f1")


def generate_purged_kfold_splits(
    n_samples: int,
    n_splits: int = 5,
    horizon: int = 5,
    embargo: int = 1,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """
    Gera índices (treino, teste) por fold temporal com purge e embargo.

    - Teste: blocos contíguos sem shuffle.
    - Purge: remove do treino observações ``i`` cujo label usa ``[i, i+horizon)``
      e sobrepõe o bloco de teste.
    - Embargo: remove do treino barras ``[test_end, test_end + embargo)``.
    """
    if n_samples < 2:
        raise ValueError(f"generate_purged_kfold_splits: n_samples={n_samples} insuficiente.")
    if n_splits < 2:
        raise ValueError(f"generate_purged_kfold_splits: n_splits deve ser >= 2, got {n_splits}.")
    if horizon < 1:
        raise ValueError(f"generate_purged_kfold_splits: horizon deve ser >= 1, got {horizon}.")
    if embargo < 0:
        raise ValueError(f"generate_purged_kfold_splits: embargo deve ser >= 0, got {embargo}.")

    indices = np.arange(n_samples)
    fold_bounds = np.linspace(0, n_samples, n_splits + 1, dtype=int)

    for k in range(n_splits):
        test_start = int(fold_bounds[k])
        test_end = int(fold_bounds[k + 1])
        if test_end <= test_start:
            continue

        train_mask = np.ones(n_samples, dtype=bool)
        train_mask[test_start:test_end] = False

        # Purge: label em i depende de i..i+horizon
        i = np.arange(n_samples)
        label_overlap = (i + horizon > test_start) & (i < test_end)
        train_mask[label_overlap] = False

        if embargo > 0:
            emb_end = min(n_samples, test_end + embargo)
            train_mask[test_end:emb_end] = False

        train_idx = indices[train_mask]
        test_idx = indices[test_start:test_end]

        if len(train_idx) < 2 or len(test_idx) < 1:
            continue

        yield train_idx, test_idx


def purged_kfold_validation(
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = 5,
    horizon: int = 5,
    embargo: int = 1,
) -> dict[str, Any]:
    """
    Validação Purged K-Fold out-of-sample.

    Reutiliza ``train_logistic_model`` e ``evaluate_classifier``.
    Sem shuffle; treino e teste preservam ordem temporal por índice.

    Parameters
    ----------
    X, y : features e labels alinhados.
    n_splits : número de folds temporais.
    horizon : horizonte do label (purge de overlap com teste).
    embargo : barras após o teste removidas do treino.

    Returns
    -------
    dict com ``fold_metrics``, ``avg_*``, ``num_folds``.
    """
    if len(X) != len(y):
        raise ValueError(
            f"purged_kfold_validation: len(X)={len(X)} != len(y)={len(y)}."
        )
    if not X.index.equals(y.index):
        raise ValueError("purged_kfold_validation: índices de X e y devem ser idênticos.")

    n = len(X)
    fold_metrics: list[dict[str, float]] = []

    for train_idx, test_idx in generate_purged_kfold_splits(
        n, n_splits=n_splits, horizon=horizon, embargo=embargo
    ):
        X_train = X.iloc[train_idx]
        y_train = y.iloc[train_idx]
        X_test = X.iloc[test_idx]
        y_test = y.iloc[test_idx]

        try:
            model = train_logistic_model(X_train, y_train)
            metrics = evaluate_classifier(model, X_test, y_test)
        except ValueError:
            continue

        fold_metrics.append({k: metrics[k] for k in _METRIC_KEYS})

    if not fold_metrics:
        raise ValueError(
            "purged_kfold_validation: nenhum fold gerado — "
            "aumente amostras ou reduza n_splits / horizon / embargo."
        )

    num_folds = len(fold_metrics)
    averages = {
        f"avg_{k}": sum(f[k] for f in fold_metrics) / num_folds for k in _METRIC_KEYS
    }

    return {
        "fold_metrics": fold_metrics,
        **averages,
        "num_folds": num_folds,
    }
