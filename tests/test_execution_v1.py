"""
Testes do Execution Engine v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.execution import simulate_execution
from microstructure.features.datasets import build_dataset
from microstructure.signal.signal_engine import generate_signals


def _ohlcv(n: int = 200, seed: int = 42) -> pd.DataFrame:
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


class TestSimulateExecution:
    def test_runs_without_error(self):
        signals = pd.Series([0, 1, 1, -1, 0], index=pd.date_range("2024-01-01", periods=5, freq="min"))
        df, metrics = simulate_execution(signals)
        assert len(df) == 5
        assert metrics is not None

    def test_position_mapping(self):
        signals = pd.Series([1, -1, 0, 1])
        df, _ = simulate_execution(signals, position_size=2.0)
        assert list(df["current_position"]) == [2.0, -2.0, 0.0, 2.0]

    def test_order_count_and_changes(self):
        signals = pd.Series([0, 1, 1, -1, 0])
        df, metrics = simulate_execution(signals)
        assert metrics["num_orders"] == int(df["executed_orders"].sum())
        assert (df["position_changes"] != 0).sum() == metrics["num_orders"]

    def test_metrics_keys(self):
        signals = pd.Series([0, 1, -1, 0])
        _, metrics = simulate_execution(signals)
        assert set(metrics.keys()) == {
            "num_orders",
            "long_entries",
            "short_entries",
            "flat_periods",
        }

    def test_gross_exposure_scales_with_capital(self):
        signals = pd.Series([1, -1])
        df_lo, _ = simulate_execution(signals, initial_capital=50_000.0)
        df_hi, _ = simulate_execution(signals, initial_capital=100_000.0)
        assert df_hi["gross_exposure"].iloc[0] == pytest.approx(2 * df_lo["gross_exposure"].iloc[0])

    def test_invalid_signal_raises(self):
        with pytest.raises(ValueError, match="sinais"):
            simulate_execution(pd.Series([0, 2, 1]))


class TestExecutionPipelineIntegration:
    def test_features_signals_execution(self, capsys):
        df = _ohlcv(200)
        X = build_dataset(df)
        X = generate_signals(X)

        exec_df, metrics = simulate_execution(
            X["signal"],
            initial_capital=100_000.0,
            position_size=1.0,
        )

        assert len(exec_df) == len(X)
        assert exec_df.index.equals(X.index)
        for col in (
            "current_position",
            "position_changes",
            "executed_orders",
            "gross_exposure",
        ):
            assert col in exec_df.columns

        assert metrics["num_orders"] >= 0
        assert metrics["flat_periods"] >= 0

        print(f"num_orders: {metrics['num_orders']}, long: {metrics['long_entries']}")
        print("EXECUTION V1 OK")

        captured = capsys.readouterr()
        assert "EXECUTION V1 OK" in captured.out
