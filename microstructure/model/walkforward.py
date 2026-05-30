"""
microstructure/model/walkforward.py — validação walk-forward (janela expansiva).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from microstructure.model.metrics import evaluate_classifier
from microstructure.model.trainer import train_logistic_model

_METRIC_KEYS = ("accuracy", "precision", "recall", "f1")


def walk_forward_validation(
    X: pd.DataFrame,
    y: pd.Series,
    train_size: float = 0.70,
    step_size: int = 20,
) -> dict[str, Any]:
    """
    Walk-forward out-of-sample com janela de treino expansiva.

    Para cada fold ``k``:
    - treino: ``X[0 : t_k]``, ``y[0 : t_k]``  (sempre antes do teste)
    - teste:  ``X[t_k : t_k + step_size]`` (ou até o fim na última janela parcial)
    - ``t_0 = floor(n * train_size)``; ``t_{k+1} = t_k + len(teste_k)``

    Sem shuffle. Reutiliza ``train_logistic_model`` e ``evaluate_classifier``.

    Parameters
    ----------
    X, y : matriz e labels alinhados temporalmente.
    train_size : fração inicial mínima para o primeiro treino (0, 1).
    step_size : barras OOS por fold (>= 1).

    Returns
    -------
    dict com ``fold_metrics``, médias ``avg_*``, e ``num_folds``.
    """
    if not 0.0 < train_size < 1.0:
        raise ValueError(
            f"walk_forward_validation: train_size deve estar em (0, 1), got {train_size}."
        )
    if step_size < 1:
        raise ValueError(
            f"walk_forward_validation: step_size deve ser >= 1, got {step_size}."
        )
    if len(X) != len(y):
        raise ValueError(
            f"walk_forward_validation: len(X)={len(X)} != len(y)={len(y)}."
        )
    if not X.index.equals(y.index):
        raise ValueError("walk_forward_validation: índices de X e y devem ser idênticos.")

    n = len(X)
    min_train = int(n * train_size)
    if min_train < 1 or min_train >= n:
        raise ValueError(
            f"walk_forward_validation: min_train={min_train} inválido para n={n}."
        )

    fold_metrics: list[dict[str, float]] = []
    test_start = min_train

    while test_start < n:
        test_end = min(test_start + step_size, n)
        if test_end <= test_start:
            break

        X_train = X.iloc[:test_start]
        y_train = y.iloc[:test_start]
        X_test = X.iloc[test_start:test_end]
        y_test = y.iloc[test_start:test_end]

        try:
            model = train_logistic_model(X_train, y_train)
            metrics = evaluate_classifier(model, X_test, y_test)
        except ValueError:
            test_start = test_end
            continue

        fold_metrics.append({k: metrics[k] for k in _METRIC_KEYS})
        test_start = test_end

    if not fold_metrics:
        raise ValueError(
            "walk_forward_validation: nenhum fold gerado — "
            "aumente amostras ou ajuste train_size / step_size."
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
