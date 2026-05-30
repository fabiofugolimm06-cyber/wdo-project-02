"""
Testes do Purged K-Fold Validation v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.model import drop_nan_feature_rows, purged_kfold_validation
from microstructure.model.purged_kfold import generate_purged_kfold_splits


def _ohlcv(n: int = 400, seed: int = 42) -> pd.DataFrame:
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


class TestPurgedKfoldSplits:
    def test_generates_multiple_folds(self):
        splits = list(generate_purged_kfold_splits(200, n_splits=5, horizon=5, embargo=1))
        assert len(splits) >= 2

    def test_train_test_disjoint(self):
        for train_idx, test_idx in generate_purged_kfold_splits(100, n_splits=4, horizon=3, embargo=1):
            assert len(np.intersect1d(train_idx, test_idx)) == 0


class TestPurgedKfoldValidation:
    def test_runs_without_error(self):
        df = _ohlcv(400)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        result = purged_kfold_validation(X_ml, y_ml, n_splits=5, horizon=5, embargo=1)
        assert result is not None

    def test_metrics_and_num_folds(self):
        df = _ohlcv(500)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        result = purged_kfold_validation(X_ml, y_ml, n_splits=5, horizon=5, embargo=1)

        assert result["num_folds"] > 0
        assert len(result["fold_metrics"]) == result["num_folds"]

        for fold in result["fold_metrics"]:
            assert set(fold.keys()) == _METRIC_KEYS

        for avg_key in ("avg_accuracy", "avg_precision", "avg_recall", "avg_f1"):
            assert avg_key in result

    def test_invalid_n_splits_raises(self):
        df = _ohlcv(100)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        with pytest.raises(ValueError, match="n_splits"):
            list(generate_purged_kfold_splits(len(X_ml), n_splits=1))


class TestPurgedKfoldPipelineIntegration:
    def test_full_pipeline(self, capsys):
        df = _ohlcv(450)
        X = build_dataset(df)
        y = create_horizon_labels(df, price_col="fechamento", horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)

        result = purged_kfold_validation(X_ml, y_ml, n_splits=5, horizon=5, embargo=1)

        assert result["num_folds"] > 0
        print(f"num_folds: {result['num_folds']}, avg_f1: {result['avg_f1']:.4f}")
        print("PURGED KFOLD V1 OK")

        captured = capsys.readouterr()
        assert "PURGED KFOLD V1 OK" in captured.out
