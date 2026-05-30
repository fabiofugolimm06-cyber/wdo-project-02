"""
Testes do Model Engine v1 (split temporal + logistic baseline).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from microstructure.model import (
    drop_nan_feature_rows,
    evaluate_classifier,
    generate_ml_signal,
    predict_probabilities,
    train_logistic_model,
    train_test_split_time_series,
)
from microstructure.model.pipeline import pipeline_fingerprint, run_ml_pipeline_v1
from tests.ohlcv_data import make_ohlcv


def _ohlcv(n: int = 200, seed: int = WDO_PROJECT_RANDOM_SEED) -> pd.DataFrame:
    """OHLCV determinístico (delega para ``tests.ohlcv_data.make_ohlcv``)."""
    return make_ohlcv(n=n, seed=seed)


class TestTimeSeriesSplit:
    def test_no_shuffle_preserves_order(self):
        df = _ohlcv(100)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        X_train, X_test, y_train, y_test = train_test_split_time_series(
            X_ml, y_ml, train_size=0.70
        )
        n = len(X_ml)
        split_idx = int(n * 0.70)
        assert len(X_train) == split_idx
        assert len(X_test) == n - split_idx
        assert X_train.index[-1] < X_test.index[0]
        assert y_train.index.equals(X_train.index)
        assert y_test.index.equals(X_test.index)

    def test_invalid_train_size_raises(self):
        df = _ohlcv(50)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        with pytest.raises(ValueError, match="train_size"):
            train_test_split_time_series(X_ml, y_ml, train_size=1.0)


class TestTrainer:
    def test_model_fits(self):
        df = _ohlcv(120)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        X_train, X_test, y_train, y_test = train_test_split_time_series(X_ml, y_ml)
        model = train_logistic_model(X_train, y_train)
        assert hasattr(model, "predict")
        assert hasattr(model, "predict_proba")


class TestPredictAndMetrics:
    def test_probabilities_shape(self):
        df = _ohlcv(150)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        X_train, X_test, y_train, y_test = train_test_split_time_series(X_ml, y_ml)
        model = train_logistic_model(X_train, y_train)
        proba = predict_probabilities(model, X_test)
        assert proba.shape == (len(X_test), 2)
        signals = generate_ml_signal(proba, threshold=0.55)
        assert signals.shape == (len(X_test),)
        assert set(np.unique(signals)).issubset({0, 1})

    def test_metrics_dict_keys(self):
        df = _ohlcv(150)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        X_train, X_test, y_train, y_test = train_test_split_time_series(X_ml, y_ml)
        model = train_logistic_model(X_train, y_train)
        metrics = evaluate_classifier(model, X_test, y_test)
        assert set(metrics.keys()) == {"accuracy", "precision", "recall", "f1"}
        for v in metrics.values():
            assert 0.0 <= v <= 1.0


def _run_ml_pipeline(
    df: pd.DataFrame,
    horizon: int = 5,
    train_size: float = 0.70,
) -> dict:
    """Delega ao pipeline isolado (determinístico)."""
    return run_ml_pipeline_v1(
        df,
        horizon=horizon,
        train_size=train_size,
        seed=WDO_PROJECT_RANDOM_SEED,
    )


class TestDeterminism:
    def test_x_ml_rows_stable_across_runs(self):
        """Elimina flutuação 176 vs 195: só horizon=5 reduz linhas."""
        df = _ohlcv(200, seed=WDO_PROJECT_RANDOM_SEED)
        shapes = [_run_ml_pipeline(df)["n_ml"] for _ in range(5)]
        assert shapes == [195, 195, 195, 195, 195]

    def test_pipeline_metrics_identical(self):
        df = _ohlcv(200, seed=WDO_PROJECT_RANDOM_SEED)
        a = _run_ml_pipeline(df)
        b = _run_ml_pipeline(df)
        assert pipeline_fingerprint(a) == pipeline_fingerprint(b)
        assert a["n_ml"] == b["n_ml"] == 195

    def test_build_dataset_does_not_mutate_input_df(self):
        df = _ohlcv(80)
        snapshot = df.copy(deep=True)
        build_dataset(df)
        pd.testing.assert_frame_equal(df, snapshot)


class TestModelPipelineIntegration:
    def test_full_pipeline(self, capsys):
        set_global_determinism(WDO_PROJECT_RANDOM_SEED)
        df = _ohlcv(200)
        X = build_dataset(df)
        y = create_horizon_labels(df, price_col="fechamento", horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)

        X_train, X_test, y_train, y_test = train_test_split_time_series(
            X_ml, y_ml, train_size=0.70
        )
        model = train_logistic_model(X_train, y_train)
        proba = predict_probabilities(model, X_test)
        signals = generate_ml_signal(proba, threshold=0.55)
        metrics = evaluate_classifier(model, X_test, y_test)

        assert X_ml.shape[0] == len(df) - 5
        assert X_ml.shape[0] == 195
        assert len(X_train) + len(X_test) == len(X_ml)
        assert proba.shape[0] == len(X_test)
        assert len(signals) == len(X_test)

        print(f"X_ml: {X_ml.shape}, train: {X_train.shape}, test: {X_test.shape}")
        print(f"metrics: {metrics}")
        print("MODEL V1 PIPELINE OK")

        captured = capsys.readouterr()
        assert "MODEL V1 PIPELINE OK" in captured.out
