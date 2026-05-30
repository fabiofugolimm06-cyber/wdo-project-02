"""
Determinismo global do WDO PROJECT 02 (ML pipeline).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.model import drop_nan_feature_rows, train_test_split_time_series
from tests.ohlcv_data import make_ohlcv


def _ml_row_count(df: pd.DataFrame, horizon: int = 5) -> int:
    X = build_dataset(df)
    y = create_horizon_labels(df, horizon=horizon)
    X_ml, y_ml = drop_invalid_label_rows(X, y)
    X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
    return len(X_ml)


class TestProjectDeterminism:
    def test_global_seeds_repeatable(self):
        df = make_ohlcv(200, seed=WDO_PROJECT_RANDOM_SEED)
        set_global_determinism(WDO_PROJECT_RANDOM_SEED)
        a = _ml_row_count(df)
        set_global_determinism(WDO_PROJECT_RANDOM_SEED)
        b = _ml_row_count(df)
        assert a == b == 200 - 5

    def test_make_ohlcv_same_seed_same_frame(self):
        a = make_ohlcv(100, seed=42)
        b = make_ohlcv(100, seed=42)
        pd.testing.assert_frame_equal(a, b)

    def test_build_dataset_no_mutation(self):
        df = make_ohlcv(60)
        snap = df.copy(deep=True)
        build_dataset(df)
        pd.testing.assert_frame_equal(df, snap)

    def test_split_no_shuffle(self):
        df = make_ohlcv(120)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
        X_train, X_test, _, _ = train_test_split_time_series(X_ml, y_ml, train_size=0.70)
        assert X_train.index[-1] < X_test.index[0]

    def test_drop_nan_row_count_stable(self):
        counts = []
        for _ in range(10):
            set_global_determinism(WDO_PROJECT_RANDOM_SEED)
            counts.append(_ml_row_count(make_ohlcv(200)))
        assert len(set(counts)) == 1
        assert counts[0] == 195
