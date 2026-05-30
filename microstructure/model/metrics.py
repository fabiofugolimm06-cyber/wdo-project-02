"""
microstructure/model/metrics.py — métricas de classificação no conjunto de teste.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


def evaluate_classifier(
    model: LogisticRegression,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, float]:
    """
    Avalia o classificador no hold-out temporal.

    Returns
    -------
    dict com chaves: ``accuracy``, ``precision``, ``recall``, ``f1``.
    """
    if len(X_test) == 0:
        raise ValueError("evaluate_classifier: X_test vazio.")

    y_true = np.asarray(y_test.copy(), dtype=int)
    y_pred = model.predict(X_test.copy())

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(
            precision_score(y_true, y_pred, average="binary", zero_division=0)
        ),
        "recall": float(recall_score(y_true, y_pred, average="binary", zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, average="binary", zero_division=0)),
    }
