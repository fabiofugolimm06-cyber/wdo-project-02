"""Testes do backtest engine v1."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.backtest.engine_v1 import run_backtest
from microstructure.run_pipeline import run_wdo_pipeline


def _ohlcv(n: int = 100) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="5min")
    close = np.linspace(100, 110, n, dtype="float32")
    return pd.DataFrame(
        {
            "abertura": close,
            "fechamento": close,
            "alta": close + 1,
            "baixa": close - 1,
            "volume": np.full(n, 1000.0, dtype="float32"),
        },
        index=idx,
    )


class TestRunBacktest:
    def test_returns_metrics_and_df(self):
        df = _ohlcv(80)
        signals = pd.Series(0, index=df.index, dtype="int8")
        signals.iloc[10] = 1
        signals.iloc[20] = -1

        out = run_backtest(df, signals, price_col="fechamento")

        assert "df" in out
        assert "metrics" in out
        assert len(out["df"]) == len(df)
        assert "equity" in out["df"].columns
        assert "drawdown" in out["df"].columns

    def test_metrics_keys(self):
        df = _ohlcv(50)
        signals = pd.Series(0, index=df.index)
        m = run_backtest(df, signals, price_col="fechamento")["metrics"]
        assert set(m.keys()) == {
            "total_return",
            "sharpe",
            "max_drawdown",
            "win_rate",
            "num_trades",
        }

    def test_same_index_no_shape_mismatch(self):
        df = _ohlcv(60)
        signals = pd.Series(np.random.choice([-1, 0, 1], 60), index=df.index)
        bt = run_backtest(df, signals, price_col="fechamento")
        assert len(bt["df"]) == len(df)

    def test_future_return_uses_shift(self):
        """Última barra não deve usar preço futuro inexistente."""
        df = _ohlcv(30)
        signals = pd.Series(0, index=df.index)
        bt = run_backtest(df, signals, price_col="fechamento")
        assert pd.isna(bt["df"]["future_return"].iloc[-1])


class TestPipelineIntegration:
    def test_full_pipeline(self):
        out = run_wdo_pipeline(_ohlcv(120))
        assert "metrics" in out
        assert "signal" in out["X"].columns
        assert "returns" in out["X"].columns
        assert "delta" in out["X"].columns
        assert len(out["df"]) == 120
