"""
microstructure/model/pipeline.py — pipeline ML v1 isolado e determinístico.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.model.predict import generate_ml_signal, predict_probabilities
from microstructure.model.split import train_test_split_time_series
from microstructure.model.trainer import train_logistic_model
from microstructure.model.utils import drop_nan_feature_rows
from microstructure.contracts.enforcement import validate_ml_contract
from microstructure.model.metrics import evaluate_classifier


def run_ml_pipeline_v1(
    df: pd.DataFrame,
    *,
    horizon: int = 5,
    train_size: float = 0.70,
    ml_threshold: float = 0.55,
    seed: int = WDO_PROJECT_RANDOM_SEED,
) -> dict[str, Any]:
    """
    Pipeline ML completo, isolado e reprodutível.

    Contrato ``metrics``: apenas ``accuracy``, ``precision``, ``recall``, ``f1``
    (ver ``microstructure/contracts/pipeline_schemas.py``).

    - Reinicia seeds globais a cada chamada
    - Não muta ``df`` (cópia profunda)
    - Sem shuffle; split temporal apenas
    """
    set_global_determinism(seed)
    work = df.copy(deep=True)

    X = build_dataset(work)
    y = create_horizon_labels(work, price_col="fechamento", horizon=horizon)
    X_ml, y_ml = drop_invalid_label_rows(X, y)
    X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)

    X_train, X_test, y_train, y_test = train_test_split_time_series(
        X_ml, y_ml, train_size=train_size
    )
    model = train_logistic_model(X_train, y_train)
    proba = predict_probabilities(model, X_test)
    signals = generate_ml_signal(proba, threshold=ml_threshold)
    metrics = evaluate_classifier(model, X_test, y_test)

    result = {
        "n_ml": len(X_ml),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "metrics": metrics,
        "signals": np.asarray(signals, dtype=int).copy(),
        "proba": np.asarray(proba, dtype=float).copy(),
    }
    validate_ml_contract(result)
    return result


def pipeline_fingerprint(result: dict[str, Any]) -> tuple[Any, ...]:
    """Chave hashável para comparação byte-a-byte entre execuções."""
    metrics = result["metrics"]
    metric_tuple = tuple(
        round(float(metrics[k]), 12) for k in sorted(metrics.keys())
    )
    return (
        int(result["n_ml"]),
        int(result["n_train"]),
        int(result["n_test"]),
        metric_tuple,
        np.asarray(result["signals"], dtype=int).tobytes(),
        np.asarray(result["proba"], dtype=float).tobytes(),
    )
