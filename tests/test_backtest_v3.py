"""
Validação do Backtest Engine v3 (holding, SL, TP, custos v2).

V1 e V2 não são alterados.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.backtest.engine_v1 import run_backtest
from microstructure.backtest.engine_v2 import run_backtest_v2
from microstructure.backtest.engine_v3 import run_backtest_v3, EXIT_REASONS
from microstructure.features.datasets import build_dataset
from microstructure.signal.signal_engine import generate_signals

V1_METRICS = frozenset({
    "total_return",
    "sharpe",
    "max_drawdown",
    "win_rate",
    "num_trades",
})

V3_NEW_METRICS = frozenset({
    "avg_trade_return",
    "avg_holding_period",
    "stop_loss_hits",
    "take_profit_hits",
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


def _signals(df: pd.DataFrame) -> pd.Series:
    return generate_signals(build_dataset(df))["signal"]


class TestBacktestV3Metrics:
    def test_v1_metrics_present(self):
        df = _synthetic_ohlcv()
        m = run_backtest_v3(df, _signals(df), price_col="fechamento")["metrics"]
        for key in V1_METRICS:
            assert key in m

    def test_v3_new_metrics_present(self):
        df = _synthetic_ohlcv()
        m = run_backtest_v3(df, _signals(df), price_col="fechamento")["metrics"]
        for key in V3_NEW_METRICS:
            assert key in m

    def test_v2_cost_fields_present(self):
        df = _synthetic_ohlcv()
        m = run_backtest_v3(df, _signals(df), price_col="fechamento")["metrics"]
        assert m["cost_per_trade"] == 0.0001
        assert m["slippage"] == 0.00005
        assert m["total_cost_paid"] >= 0


class TestBacktestV3Columns:
    def test_exit_reason_column(self):
        df = _synthetic_ohlcv()
        bt = run_backtest_v3(df, _signals(df), price_col="fechamento")["df"]
        assert "exit_reason" in bt.columns
        reasons = bt["exit_reason"].dropna().unique()
        assert set(reasons).issubset(EXIT_REASONS)

    def test_cost_columns_like_v2(self):
        df = _synthetic_ohlcv()
        bt = run_backtest_v3(df, _signals(df), price_col="fechamento")["df"]
        assert "trade_event" in bt.columns
        assert "cost" in bt.columns
        assert "gross_return" in bt.columns
        assert "strategy_return" in bt.columns


class TestBacktestV3ExitLogic:
    def test_stop_loss_triggers_with_tight_stop(self):
        """Queda forte após entrada long → stop_loss."""
        n = 30
        idx = pd.date_range("2024-01-01", periods=n, freq="min")
        close = np.linspace(100, 70, n, dtype=np.float32)
        df = pd.DataFrame(
            {
                "abertura": close,
                "alta": close + 1,
                "baixa": close - 1,
                "fechamento": close,
                "volume": np.full(n, 1000.0, dtype="float32"),
            },
            index=idx,
        )
        signals = pd.Series(0, index=idx, dtype=np.int8)
        signals.iloc[2] = 1

        m = run_backtest_v3(
            df,
            signals,
            price_col="fechamento",
            max_hold_bars=100,
            stop_loss=0.01,
            take_profit=0.99,
        )["metrics"]
        assert m["stop_loss_hits"] >= 1

    def test_take_profit_triggers(self):
        n = 30
        idx = pd.date_range("2024-01-01", periods=n, freq="min")
        close = np.linspace(100, 130, n, dtype=np.float32)
        df = pd.DataFrame(
            {
                "abertura": close,
                "alta": close + 1,
                "baixa": close - 1,
                "fechamento": close,
                "volume": np.full(n, 1000.0, dtype="float32"),
            },
            index=idx,
        )
        signals = pd.Series(0, index=idx, dtype=np.int8)
        signals.iloc[2] = 1

        m = run_backtest_v3(
            df,
            signals,
            price_col="fechamento",
            max_hold_bars=100,
            stop_loss=0.99,
            take_profit=0.02,
        )["metrics"]
        assert m["take_profit_hits"] >= 1

    def test_max_hold_exits(self):
        n = 50
        idx = pd.date_range("2024-01-01", periods=n, freq="min")
        close = np.full(n, 100.0, dtype=np.float32)
        df = pd.DataFrame(
            {
                "abertura": close,
                "alta": close + 0.5,
                "baixa": close - 0.5,
                "fechamento": close,
                "volume": np.full(n, 1000.0, dtype="float32"),
            },
            index=idx,
        )
        signals = pd.Series(0, index=idx, dtype=np.int8)
        signals.iloc[5] = 1

        m = run_backtest_v3(
            df,
            signals,
            price_col="fechamento",
            max_hold_bars=5,
            stop_loss=0.99,
            take_profit=0.99,
        )["metrics"]
        assert m["exit_max_hold"] >= 1

    def test_completed_trades_log(self):
        df = _synthetic_ohlcv(100)
        out = run_backtest_v3(df, _signals(df), price_col="fechamento")
        assert isinstance(out["trades"], list)
        if out["trades"]:
            t = out["trades"][0]
            assert "exit_reason" in t
            assert "holding_bars" in t
            assert "trade_return" in t


class TestBacktestV3Pipeline:
    def test_full_pipeline(self, capsys):
        df = _synthetic_ohlcv(200)
        signals = _signals(df)
        result = run_backtest_v3(
            df=df,
            signals=signals,
            price_col="fechamento",
            max_hold_bars=5,
            stop_loss=0.01,
            take_profit=0.02,
        )
        metrics = result["metrics"]
        print(metrics)

        assert -1.0 <= metrics["max_drawdown"] <= 0.0
        assert np.isfinite(metrics["total_return"])
        assert metrics["completed_trades"] >= 0

        print("BACKTEST V3 PIPELINE OK")

    def test_v3_differs_from_v2_with_same_data(self):
        """Gestão de trade v3 deve produzir resultado diferente de v2."""
        df = _synthetic_ohlcv(seed=11)
        sig = _signals(df)
        m2 = run_backtest_v2(df, sig, price_col="fechamento")["metrics"]
        m3 = run_backtest_v3(df, sig, price_col="fechamento")["metrics"]
        assert m3["total_return"] != m2["total_return"] or (
            m3["completed_trades"] != m2["num_trade_events"]
        )
