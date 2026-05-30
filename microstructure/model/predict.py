"""
microstructure/model/predict.py — probabilidades e sinal ML binário.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


def predict_probabilities(
    model: LogisticRegression,
    X_test: pd.DataFrame,
) -> np.ndarray:
    """
    Retorna ``model.predict_proba(X_test)``.

    Shape típico: ``(n_samples, 2)`` — coluna 1 = P(classe 1).
    """
    if len(X_test) == 0:
        raise ValueError("predict_probabilities: X_test vazio.")

    return model.predict_proba(X_test.copy())


def generate_ml_signal(
    probabilities: np.ndarray,
    threshold: float = 0.55,
) -> np.ndarray:
    """
    Converte probabilidades em sinal binário {0, 1}.

    - Se ``probabilities`` é 2D, usa a coluna da classe positiva (índice 1).
    - ``1`` se prob >= ``threshold``, senão ``0``.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(
            f"generate_ml_signal: threshold deve estar em [0, 1], got {threshold}."
        )

    arr = np.asarray(probabilities, dtype=float)
    if arr.ndim == 2:
        if arr.shape[1] < 2:
            raise ValueError(
                f"generate_ml_signal: esperado 2 colunas em predict_proba, got shape={arr.shape}."
            )
        probs = arr[:, 1]
    elif arr.ndim == 1:
        probs = arr
    else:
        raise ValueError(f"generate_ml_signal: shape inválido {arr.shape}.")

    return (probs >= threshold).astype(int)
