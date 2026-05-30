"""
Testes do Label Engine v1 (horizon labels + triple barrier skeleton).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.features.datasets import build_dataset
from microstructure.labeling.horizon import create_horizon_labels
from microstructure.labeling.triple_barrier import create_triple_barrier_labels
from microstructure.labeling.utils import drop_invalid_label_rows


def _ohlcv(n: int = 100, seed: int = 42) -> pd.DataFrame:
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


class TestHorizonLabels:
    def test_series_length_matches_df(self):
        df = _ohlcv(80)
        y = create_horizon_labels(df, horizon=5)
        assert len(y) == len(df)

    def test_index_aligned(self):
        df = _ohlcv(50)
        y = create_horizon_labels(df, horizon=3)
        assert y.index.equals(df.index)

    def test_values_only_zero_one_on_valid(self):
        df = _ohlcv(60)
        y = create_horizon_labels(df, horizon=5)
        valid = y.dropna()
        assert set(valid.unique()).issubset({0, 1})

    def test_last_horizon_rows_are_nan(self):
        horizon = 5
        df = _ohlcv(30)
        y = create_horizon_labels(df, horizon=horizon)
        assert y.iloc[-horizon:].isna().all()
        assert pd.notna(y.iloc[-(horizon + 1)])

    def test_label_matches_manual_future_return(self):
        df = _ohlcv(20)
        horizon = 3
        price = df["fechamento"].astype(float)
        y = create_horizon_labels(df, horizon=horizon)
        t = 5
        fr = price.iloc[t + horizon] / price.iloc[t] - 1
        expected = 1 if fr > 0 else 0
        assert int(y.iloc[t]) == expected

    def test_integer_index_raises(self):
        df = _ohlcv(10).reset_index(drop=True)
        with pytest.raises(TypeError, match="DatetimeIndex"):
            create_horizon_labels(df)

    def test_no_leakage_changing_future_price_does_not_affect_past_label(self):
        """Alterar preço em t+h não deve mudar y[t'] para t' < t."""
        df = _ohlcv(40)
        horizon = 5
        y1 = create_horizon_labels(df, horizon=horizon)
        df2 = df.copy()
        inject = 20
        df2.at[df2.index[inject], "fechamento"] = 99999.0
        y2 = create_horizon_labels(df2, horizon=horizon)
        safe_end = inject - horizon
        assert y1.iloc[:safe_end].equals(y2.iloc[:safe_end])


class TestDropInvalidRows:
    def test_supervised_dataset_shape(self):
        df = _ohlcv(100)
        horizon = 5
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=horizon)
        X_clean, y_clean = drop_invalid_label_rows(X, y)
        assert len(X_clean) == len(df) - horizon
        assert len(y_clean) == len(X_clean)
        assert y_clean.isna().sum() == 0


class TestTripleBarrierSkeleton:
    def test_not_implemented_yet(self):
        df = _ohlcv(30)
        with pytest.raises(NotImplementedError, match="v2"):
            create_triple_barrier_labels(df)

    def test_validates_input_before_not_implemented(self):
        df = _ohlcv(10).reset_index(drop=True)
        with pytest.raises(TypeError):
            create_triple_barrier_labels(df)


class TestPipelineIntegration:
    def test_x_y_ready_for_model(self, capsys):
        df = _ohlcv(200)
        X = build_dataset(df)
        y = create_horizon_labels(df, horizon=5)
        X_ml, y_ml = drop_invalid_label_rows(X, y)
        print(f"X: {X_ml.shape}, y: {y_ml.shape}")
        assert X_ml.shape[0] == 195
        assert X_ml.shape[1] >= 1
        print("LABEL ENGINE V1 OK")
