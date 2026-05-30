"""
microstructure/model/trainer.py — treino baseline (Logistic Regression).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from microstructure.model.utils import drop_nan_feature_rows


def train_logistic_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> LogisticRegression:
    """
    Treina regressão logística sobre features tabulares.

    Parameters
    ----------
    X_train : matriz de features (sem colunas não numéricas extras).
    y_train : labels binários {0, 1}.

    Returns
    -------
    model : ``LogisticRegression`` ajustado.
    """
    if len(X_train) == 0:
        raise ValueError("train_logistic_model: X_train vazio.")

    if len(X_train) != len(y_train):
        raise ValueError(
            f"train_logistic_model: len(X_train)={len(X_train)} != len(y_train)={len(y_train)}."
        )

    y = np.asarray(y_train, dtype=int)
    classes = np.unique(y[~np.isnan(y)])
    if not set(classes).issubset({0, 1}):
        raise ValueError(
            f"train_logistic_model: y_train deve conter apenas 0 e 1, got classes={classes}."
        )
    if len(classes) < 2:
        raise ValueError(
            "train_logistic_model: y_train precisa de pelo menos duas classes (0 e 1)."
        )

    set_global_determinism(WDO_PROJECT_RANDOM_SEED)

    X_fit, y_fit = drop_nan_feature_rows(
        X_train.copy(),
        y_train.copy(),
    )

    model = LogisticRegression(max_iter=1000, random_state=WDO_PROJECT_RANDOM_SEED)
    model.fit(X_fit, np.asarray(y_fit, dtype=int))
    return model
