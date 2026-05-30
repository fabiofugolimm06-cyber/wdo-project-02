"""Testes do signal engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.signal.signal_engine import generate_signals


def _feature_matrix(n: int = 20) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="5min")
    return pd.DataFrame(
        {
            "returns": np.linspace(-0.02, 0.02, n, dtype="float32"),
            "delta": np.linspace(-5, 5, n, dtype="float32"),
        },
        index=idx,
    )


class TestGenerateSignals:
    def test_adds_signal_column(self):
        X = _feature_matrix()
        out = generate_signals(X)
        assert "signal" in out.columns
        assert "signal" not in X.columns

    def test_buy_rule(self):
        X = pd.DataFrame({"returns": [0.01], "delta": [1.0]})
        assert generate_signals(X)["signal"].iloc[0] == 1

    def test_sell_rule(self):
        X = pd.DataFrame({"returns": [-0.01], "delta": [-1.0]})
        assert generate_signals(X)["signal"].iloc[0] == -1

    def test_neutral_mixed_signs(self):
        X = pd.DataFrame({"returns": [0.01], "delta": [-1.0]})
        assert generate_signals(X)["signal"].iloc[0] == 0

    def test_neutral_zero(self):
        X = pd.DataFrame({"returns": [0.0], "delta": [0.0]})
        assert generate_signals(X)["signal"].iloc[0] == 0

    def test_vectorized_length(self):
        X = _feature_matrix(100)
        out = generate_signals(X)
        assert len(out) == 100
        assert set(out["signal"].unique()).issubset({-1, 0, 1})

    def test_missing_columns_raises(self):
        with pytest.raises(ValueError, match="ausentes"):
            generate_signals(pd.DataFrame({"delta": [1.0]}))

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="vazio"):
            generate_signals(pd.DataFrame())
