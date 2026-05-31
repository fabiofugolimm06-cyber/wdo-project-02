"""
microstructure/pipeline/end_to_end.py — pipeline integrado (Stage 10).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from microstructure.contracts.enforcement import validate_full_pipeline_contract
from microstructure.determinism import set_global_determinism
from microstructure.backtest.engine_v3 import run_backtest_v3
from microstructure.execution import simulate_execution
from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.model import (
    drop_nan_feature_rows,
    evaluate_classifier,
    generate_ml_signal,
    predict_probabilities,
    train_logistic_model,
    train_test_split_time_series,
)


def run_full_pipeline(
    df: pd.DataFrame,
    price_col: str = "fechamento",
    horizon: int = 5,
    train_size: float = 0.70,
    ml_threshold: float = 0.55,
    initial_capital: float = 100_000.0,
    position_size: float = 1.0,
) -> dict[str, Any]:
    """
    Pipeline ponta a ponta: FEATURES → LABELS → MODEL → EXECUTION → BACKTEST.

    Orquestra módulos existentes sem alterá-los. Sinais de trading vêm do modelo ML
    (``generate_ml_signal``) no conjunto de teste temporal.

    Parameters
    ----------
    df : OHLCV com ``DatetimeIndex``.
    price_col : coluna de preço (labels + backtest).
    horizon : horizonte das labels.
    train_size : fração para treino no split temporal.
    ml_threshold : limiar de probabilidade para sinal ML.
    initial_capital, position_size : parâmetros de ``simulate_execution``.

    Returns
    -------
    dict com ``features_shape``, ``model_metrics`` (ML only),
    ``execution_metrics``, ``backtest_metrics`` (inclui ``sharpe``).

    Contratos: ``microstructure/contracts/pipeline_schemas.py``.
    """
    if df is None or len(df) == 0:
        raise ValueError("run_full_pipeline: DataFrame vazio.")

    set_global_determinism()
    df = df.copy()

    # 1. Features
    X = build_dataset(df)

    # 2–4. Labels + limpeza
    y = create_horizon_labels(df, price_col=price_col, horizon=horizon)
    X_ml, y_ml = drop_invalid_label_rows(X, y)
    X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
    features_shape = tuple(X_ml.shape)

    # 5–8. Model (treino / teste / previsão / sinal ML)
    X_train, X_test, y_train, y_test = train_test_split_time_series(
        X_ml, y_ml, train_size=train_size
    )
    model = train_logistic_model(X_train, y_train)
    proba = predict_probabilities(model, X_test)
    ml_signal_arr = generate_ml_signal(proba, threshold=ml_threshold)
    ml_signals = pd.Series(ml_signal_arr, index=X_test.index, name="signal")

    model_metrics = evaluate_classifier(model, X_test, y_test)

    # 9. Execution (sinais ML no hold-out)
    _, execution_metrics = simulate_execution(
        ml_signals,
        initial_capital=initial_capital,
        position_size=position_size,
    )

    # 10. Backtest v3 (mesmo hold-out alinhado a ``df``)
    df_test = df.loc[X_test.index]
    bt_out = run_backtest_v3(df_test, ml_signals, price_col=price_col)
    backtest_metrics = bt_out["metrics"]

    result = {
        "features_shape": features_shape,
        "model_metrics": model_metrics,
        "execution_metrics": execution_metrics,
        "backtest_metrics": backtest_metrics,
    }
    validate_full_pipeline_contract(result)
    return result
