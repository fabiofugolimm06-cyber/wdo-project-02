"""
Validação do Backtest Engine v2 (custos + slippage).

V1 permanece baseline — não alterado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.backtest.engine_v1 import run_backtest
from microstructure.backtest.engine_v2 import run_backtest_v2
from microstructure.features.datasets import build_dataset
from microstructure.signal.signal_engine import generate_signals

METRIC_KEYS = frozenset({
    "total_return",
    "sharpe",
    "max_drawdown",
    "win_rate",
    "num_trades",
})


def _synthetic_ohlcv(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    fechamento = price.astype(np.float32)
    abertura = (fechamento + rng.normal(0, 0.1, n)).astype(np.float32)
    alta = (np.maximum(abertura, fechamento) + np.abs(rng.normal(0, 0.1, n))).astype(
        np.float32
    )
    baixa = (np.minimum(abertura, fechamento) - np.abs(rng.normal(0, 0.1, n))).astype(
        np.float32
    )
    volume = rng.integers(100, 1000, size=n).astype(np.float32)
    return pd.DataFrame(
        {
            "abertura": abertura,
            "alta": alta,
            "baixa": baixa,
            "fechamento": fechamento,
            "volume": volume,
        },
        index=idx,
    )


def _pipeline_signals(df: pd.DataFrame) -> pd.Series:
    X = generate_signals(build_dataset(df))
    return X["signal"]


class TestBacktestV2Metrics:
    def test_all_v1_metrics_present(self):
        df = _synthetic_ohlcv()
        signals = _pipeline_signals(df)
        result = run_backtest_v2(df, signals, price_col="fechamento")
        for key in METRIC_KEYS:
            assert key in result["metrics"]

    def test_v2_extra_cost_metrics(self):
        df = _synthetic_ohlcv()
        signals = _pipeline_signals(df)
        m = run_backtest_v2(df, signals, price_col="fechamento")["metrics"]
        assert m["cost_per_trade"] == 0.0001
        assert m["slippage"] == 0.00005
        assert m["total_cost_paid"] >= 0
        assert m["num_trade_events"] >= 0


class TestBacktestV2Costs:
    def test_cost_columns_in_df(self):
        df = _synthetic_ohlcv()
        signals = _pipeline_signals(df)
        bt = run_backtest_v2(df, signals, price_col="fechamento")["df"]
        assert "trade_event" in bt.columns
        assert "cost" in bt.columns
        assert "gross_return" in bt.columns

    def test_cost_applied_only_on_trade_events(self):
        df = _synthetic_ohlcv()
        signals = _pipeline_signals(df)
        bt = run_backtest_v2(
            df,
            signals,
            price_col="fechamento",
            cost_per_trade=0.001,
            slippage=0.001,
        )["df"]
        mask = bt["trade_event"] == 0
        assert (bt.loc[mask, "cost"] == 0).all()
        assert (bt.loc[~mask, "cost"] > 0).any()

    def test_strategy_return_equals_gross_minus_cost(self):
        df = _synthetic_ohlcv()
        signals = _pipeline_signals(df)
        bt = run_backtest_v2(df, signals, price_col="fechamento")["df"]
        np.testing.assert_allclose(
            bt["strategy_return"],
            bt["gross_return"] - bt["cost"],
            rtol=1e-6,
            equal_nan=True,
        )

    def test_v2_total_return_lower_than_v1_with_same_cost_params_zero(self):
        """Com custos > 0, v2 deve penalizar retorno vs v1."""
        df = _synthetic_ohlcv(seed=99)
        signals = _pipeline_signals(df)
        m1 = run_backtest(df, signals, price_col="fechamento")["metrics"]
        m2 = run_backtest_v2(
            df,
            signals,
            price_col="fechamento",
            cost_per_trade=0.0001,
            slippage=0.00005,
        )["metrics"]
        assert m2["total_return"] <= m1["total_return"]

    def test_higher_costs_reduce_return_further(self):
        df = _synthetic_ohlcv(seed=7)
        signals = _pipeline_signals(df)
        low = run_backtest_v2(
            df, signals, price_col="fechamento", cost_per_trade=0.0001, slippage=0.00005
        )["metrics"]["total_return"]
        high = run_backtest_v2(
            df, signals, price_col="fechamento", cost_per_trade=0.01, slippage=0.01
        )["metrics"]["total_return"]
        assert high <= low


class TestBacktestV2Pipeline:
    def test_full_pipeline_v2(self, capsys):
        df = _synthetic_ohlcv(200)
        signals = _pipeline_signals(df)
        result = run_backtest_v2(
            df=df,
            signals=signals,
            price_col="fechamento",
        )
        metrics = result["metrics"]
        print(metrics)

        assert -1.0 <= metrics["max_drawdown"] <= 0.0
        assert np.isfinite(metrics["total_return"])
        assert metrics["total_cost_paid"] > 0

        print("BACKTEST V2 PIPELINE OK")
