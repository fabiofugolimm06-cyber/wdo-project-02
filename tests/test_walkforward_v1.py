"""
Testes do Walk-Forward Validation v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.model import drop_nan_feature_rows, walk_forward_validation


def _ohlcv(n: int = 300, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    fechamento = price.astype(np.float32)
    return pd.DataFrame(
        {
            "abertura": fechamento,
            "alta": fechamento + 1,
            "baixa": fechamento - 1,
            "fechamento": fechamento,
            "volume": rng.integers(100, 1000, n).astype(np.float32),
        },
        index=idx,
    )


_METRIC_KEYS = {"accuracy", "precision", "recall", "f1"}


class TestWalkForwardValidation:
    def test_runs_without_error(self):
        df = _ohlcv(300)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        result = walk_forward_validation(X_ml, y_ml, train_size=0.70, step_size=20)
        assert result is not None

    def test_multiple_folds_and_metrics(self):
        df = _ohlcv(400)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        result = walk_forward_validation(X_ml, y_ml, train_size=0.70, step_size=20)

        assert result["num_folds"] > 1
        assert len(result["fold_metrics"]) == result["num_folds"]

        for fold in result["fold_metrics"]:
            assert set(fold.keys()) == _METRIC_KEYS
            for k in _METRIC_KEYS:
                assert 0.0 <= fold[k] <= 1.0

        for avg_key in ("avg_accuracy", "avg_precision", "avg_recall", "avg_f1"):
            assert avg_key in result
            assert 0.0 <= result[avg_key] <= 1.0

    def test_invalid_step_size_raises(self):
        df = _ohlcv(100)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        with pytest.raises(ValueError, match="step_size"):
            walk_forward_validation(X_ml, y_ml, step_size=0)


class TestWalkForwardPipelineIntegration:
    def test_full_pipeline(self, capsys):
        df = _ohlcv(350)
        X = build_dataset(df)
        y = create_horizon_labels(df, price_col="fechamento", horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)

        result = walk_forward_validation(X_ml, y_ml, train_size=0.70, step_size=20)

        assert result["num_folds"] > 0
        print(f"num_folds: {result['num_folds']}, avg_f1: {result['avg_f1']:.4f}")
        print("WALK FORWARD V1 OK")

        captured = capsys.readouterr()
        assert "WALK FORWARD V1 OK" in captured.out
