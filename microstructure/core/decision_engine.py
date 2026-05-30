"""
microstructure/core/decision_engine.py — Decision Core Unification (v1).
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.model import (
    drop_nan_feature_rows,
    predict_probabilities,
    train_logistic_model,
    train_test_split_time_series,
)
from microstructure.model.predict import generate_ml_signal
from microstructure.risk.risk_engine import risk_filter
from microstructure.signal.signal_engine import generate_signals

DecisionMode = Literal["signal_only", "ml", "hybrid"]
_VALID_MODES = frozenset({"signal_only", "ml", "hybrid"})
_VALID_SIGNALS = {-1, 0, 1}


def _validate_df(df: pd.DataFrame) -> None:
    if df is None or len(df) == 0:
        raise ValueError("run_decision_pipeline: DataFrame vazio.")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("run_decision_pipeline: índice deve ser DatetimeIndex.")
    if not df.index.is_monotonic_increasing:
        raise ValueError("run_decision_pipeline: índice deve ser monotônico crescente.")


def _rule_signals(X: pd.DataFrame) -> pd.Series:
    return generate_signals(X)["signal"].astype(int)


def _ml_signals_from_model(
    X: pd.DataFrame,
    model: LogisticRegression,
    threshold: float,
) -> pd.Series:
    """Sinais ML {0,1} alinhados ao índice de X (NaN → 0)."""
    out = pd.Series(0, index=X.index, dtype=int, name="signal")
    valid = X.notna().all(axis=1)
    if not valid.any():
        return out

    proba = predict_probabilities(model, X.loc[valid])
    ml = generate_ml_signal(proba, threshold=threshold)
    out.loc[valid] = ml.astype(int)
    return out


def _ml_signals_oos(
    df: pd.DataFrame,
    X: pd.DataFrame,
    threshold: float,
    price_col: str,
    horizon: int,
    train_size: float,
) -> pd.Series:
    """
    Prevê apenas no hold-out temporal; treino = zeros (sem lookahead de labels no OOS).
    """
    y = create_horizon_labels(df, price_col=price_col, horizon=horizon)
    X_ml, y_ml = drop_invalid_label_rows(X, y)
    X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
    X_train, X_test, y_train, _ = train_test_split_time_series(
        X_ml, y_ml, train_size=train_size
    )
    if len(X_test) == 0:
        raise ValueError("run_decision_pipeline: conjunto de teste vazio após split.")

    fitted = train_logistic_model(X_train, y_train)
    out = pd.Series(0, index=X.index, dtype=int, name="signal")
    test_sig = _ml_signals_from_model(X_test, fitted, threshold)
    out.loc[X_test.index] = test_sig
    return out


def _hybrid_combine(rule: pd.Series, ml: pd.Series) -> pd.Series:
    """
    Combinação simples rule + ML (ML long-only 0/1).

    - Compra: rule==1 e ML==1
    - Venda: rule==-1 e ML==0
    - Caso contrário: flat
    """
    rule = rule.reindex(ml.index).fillna(0).astype(int)
    ml = ml.astype(int)
    sig = np.zeros(len(ml), dtype=int)
    sig[(rule.to_numpy() == 1) & (ml.to_numpy() == 1)] = 1
    sig[(rule.to_numpy() == -1) & (ml.to_numpy() == 0)] = -1
    return pd.Series(sig, index=ml.index, name="signal")


def _apply_risk_layer(
    signals: pd.Series,
    allow_trading: bool,
) -> pd.Series:
    filtered = risk_filter(signals, allow_trading=allow_trading)
    out = filtered["signals"]
    if isinstance(out, pd.Series):
        return out.astype(int)
    return pd.Series(out.astype(int), index=signals.index, name="signal")


def run_decision_pipeline(
    df: pd.DataFrame,
    mode: str = "signal_only",
    model: LogisticRegression | None = None,
    threshold: float = 0.55,
    price_col: str = "fechamento",
    horizon: int = 5,
    train_size: float = 0.70,
    apply_risk: bool = True,
    allow_trading: bool = True,
) -> dict[str, Any]:
    """
    Núcleo único de decisão: features → sinais → risco (opcional).

    Parameters
    ----------
    df : OHLCV com DatetimeIndex.
    mode : ``signal_only`` | ``ml`` | ``hybrid``.
    model : modelo pré-treinado (``ml`` / ``hybrid``). Se ``None``, treino temporal interno.
    threshold : limiar para ``generate_ml_signal``.
    price_col, horizon, train_size : usados só para treino interno de labels.
    apply_risk : aplica ``risk_filter`` na saída.
    allow_trading : flag passada ao risk layer.

    Returns
    -------
    dict com ``signals``, ``features``, ``mode``, ``model_used``, ``timestamp_index``.
    """
    if mode not in _VALID_MODES:
        raise ValueError(
            f"run_decision_pipeline: mode inválido {mode!r}. "
            f"Use: {sorted(_VALID_MODES)}."
        )
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"run_decision_pipeline: threshold inválido {threshold}.")

    _validate_df(df)
    X = build_dataset(df)
    model_used = False

    if mode == "signal_only":
        signals = _rule_signals(X)

    elif mode == "ml":
        if model is not None:
            model_used = True
            signals = _ml_signals_from_model(X, model, threshold)
        else:
            signals = _ml_signals_oos(
                df, X, threshold, price_col, horizon, train_size
            )
            model_used = True

    else:  # hybrid
        rule = _rule_signals(X)
        if model is not None:
            model_used = True
            ml = _ml_signals_from_model(X, model, threshold)
        else:
            ml = _ml_signals_oos(
                df, X, threshold, price_col, horizon, train_size
            )
            model_used = True
        signals = _hybrid_combine(rule, ml)

    if apply_risk:
        signals = _apply_risk_layer(signals, allow_trading=allow_trading)

    unique = set(signals.unique())
    if not unique.issubset(_VALID_SIGNALS):
        raise ValueError(f"run_decision_pipeline: sinais inválidos {unique}.")

    return {
        "signals": signals.astype(int),
        "features": X.copy(),
        "mode": mode,
        "model_used": model_used,
        "timestamp_index": df.index.copy(),
    }

