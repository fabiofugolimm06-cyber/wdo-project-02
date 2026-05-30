"""
microstructure/optimization/grid_search_v1.py — grid search temporal (v1).
"""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from microstructure.model.metrics import evaluate_classifier
from microstructure.model.split import train_test_split_time_series
from microstructure.model.trainer import train_logistic_model
from microstructure.model.utils import drop_nan_feature_rows

_SCORING_METRICS = frozenset({"accuracy", "precision", "recall", "f1"})
_SPLIT_PARAMS = frozenset({"train_size"})
_MODEL_PARAMS = frozenset({
    "C",
    "penalty",
    "class_weight",
    "solver",
    "max_iter",
})
_DEFAULT_TRAIN_SIZE = 0.70


def _expand_param_grid(param_grid: dict[str, Any]) -> list[dict[str, Any]]:
    if not param_grid:
        raise ValueError("run_grid_search: param_grid vazio.")

    keys = list(param_grid.keys())
    value_lists: list[list[Any]] = []
    for key in keys:
        values = param_grid[key]
        if not isinstance(values, (list, tuple)):
            values = [values]
        if len(values) == 0:
            raise ValueError(f"run_grid_search: param_grid['{key}'] vazio.")
        value_lists.append(list(values))

    combos: list[dict[str, Any]] = []
    for product_values in itertools.product(*value_lists):
        combos.append(dict(zip(keys, product_values)))
    return combos


def _train_logistic_with_params(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_params: dict[str, Any],
) -> LogisticRegression:
    """Treino com hiperparâmetros sklearn (mesma validação que trainer v1)."""
    if len(X_train) == 0:
        raise ValueError("grid_search: X_train vazio.")

    y = np.asarray(y_train, dtype=int)
    classes = np.unique(y[~np.isnan(y)])
    if len(classes) < 2:
        raise ValueError("grid_search: y_train precisa de duas classes.")

    set_global_determinism(WDO_PROJECT_RANDOM_SEED)
    X_fit, y_fit = drop_nan_feature_rows(X_train.copy(), y_train.copy())
    lr_kwargs = {
        **model_params,
        "random_state": WDO_PROJECT_RANDOM_SEED,
        "solver": "lbfgs",
        "warm_start": False,
    }
    if "max_iter" not in lr_kwargs:
        lr_kwargs["max_iter"] = 1000

    model = LogisticRegression(**lr_kwargs)
    model.fit(X_fit, np.asarray(y_fit, dtype=int))
    return model


def run_grid_search(
    X: pd.DataFrame,
    y: pd.Series,
    param_grid: dict[str, list[Any]],
    scoring: str = "f1",
    train_size: float = _DEFAULT_TRAIN_SIZE,
) -> dict[str, Any]:
    """
    Grid search com split temporal (sem shuffle).

    Parâmetros de split
    -------------------
    ``train_size`` em ``param_grid`` ou argumento fixo.

    Parâmetros de modelo
    --------------------
    Chaves sklearn suportadas: ``C``, ``penalty``, ``class_weight``, ``solver``, ``max_iter``.
    Se ausentes, usa ``train_logistic_model()`` (baseline v1).

    Parameters
    ----------
    X, y : features e labels alinhados.
    param_grid : dict de listas (ex.: ``{"C": [0.1, 1.0], "train_size": [0.7, 0.8]}``).
    scoring : métrica de ``evaluate_classifier`` para ranquear.

    Returns
    -------
    {"best_params", "best_score", "all_results"}
    """
    if scoring not in _SCORING_METRICS:
        raise ValueError(
            f"run_grid_search: scoring deve ser um de {_SCORING_METRICS}, got {scoring!r}."
        )
    if len(X) != len(y):
        raise ValueError(f"run_grid_search: len(X)={len(X)} != len(y)={len(y)}.")
    if not X.index.equals(y.index):
        raise ValueError("run_grid_search: índices de X e y devem ser idênticos.")

    unknown = set(param_grid.keys()) - _SPLIT_PARAMS - _MODEL_PARAMS
    if unknown:
        raise ValueError(
            f"run_grid_search: chaves não suportadas: {sorted(unknown)}."
        )

    combinations = _expand_param_grid(param_grid)
    all_results: list[dict[str, Any]] = []
    best_params: dict[str, Any] | None = None
    best_score = float("-inf")
    best_metrics: dict[str, float] | None = None

    for params in combinations:
        combo_train_size = float(params.get("train_size", train_size))
        if not 0.0 < combo_train_size < 1.0:
            raise ValueError(
                f"run_grid_search: train_size inválido {combo_train_size}."
            )

        model_params = {
            k: v for k, v in params.items() if k in _MODEL_PARAMS
        }

        X_train, X_test, y_train, y_test = train_test_split_time_series(
            X, y, train_size=combo_train_size
        )

        try:
            if model_params:
                model = _train_logistic_with_params(X_train, y_train, model_params)
            else:
                model = train_logistic_model(X_train, y_train)
            metrics = evaluate_classifier(model, X_test, y_test)
        except ValueError:
            continue

        score = float(metrics[scoring])
        record = {
            "params": dict(params),
            "score": score,
            "metrics": metrics,
        }
        all_results.append(record)

        if score > best_score:
            best_score = score
            best_params = dict(params)
            best_metrics = metrics

    if not all_results or best_params is None:
        raise ValueError(
            "run_grid_search: nenhuma combinação válida — "
            "revise param_grid ou tamanho de X/y."
        )

    return {
        "best_params": best_params,
        "best_score": best_score,
        "best_metrics": best_metrics,
        "all_results": all_results,
    }
