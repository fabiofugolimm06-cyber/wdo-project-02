"""
Testes do Risk Engine v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.execution import simulate_execution
from microstructure.features.datasets import build_dataset
from microstructure.risk import (
    calculate_position_size,
    check_daily_loss_limit,
    check_max_drawdown,
    risk_filter,
)
from microstructure.signal.signal_engine import generate_signals


class TestCalculatePositionSize:
    def test_basic_sizing(self):
        out = calculate_position_size(
            capital=100_000.0,
            risk_per_trade=0.01,
            stop_loss_pct=0.01,
        )
        assert out["position_size"] == pytest.approx(1.0)

    def test_stop_zero_raises(self):
        with pytest.raises(ValueError, match="stop_loss_pct"):
            calculate_position_size(100_000.0, 0.01, 0.0)

    def test_invalid_capital_raises(self):
        with pytest.raises(ValueError, match="capital"):
            calculate_position_size(0, 0.01, 0.01)


class TestDailyLossLimit:
    def test_within_limit(self):
        assert check_daily_loss_limit(-100.0, -150.0)["risk_allowed"] is True

    def test_breach_limit(self):
        assert check_daily_loss_limit(-200.0, -150.0)["risk_allowed"] is False

    def test_positive_limit_raises(self):
        with pytest.raises(ValueError, match="daily_loss_limit"):
            check_daily_loss_limit(0.0, 100.0)


class TestMaxDrawdown:
    def test_within_drawdown(self):
        assert check_max_drawdown(-0.05, -0.10)["risk_allowed"] is True

    def test_breach_drawdown(self):
        assert check_max_drawdown(-0.15, -0.10)["risk_allowed"] is False

    def test_positive_drawdown_raises(self):
        with pytest.raises(ValueError, match="current_drawdown"):
            check_max_drawdown(0.01, -0.10)


class TestRiskFilter:
    def test_blocks_signals_when_disabled(self):
        signals = pd.Series([1, -1, 0, 1])
        out = risk_filter(signals, allow_trading=False)
        assert list(out["signals"]) == [0, 0, 0, 0]
        assert out["trading_enabled"] is False
        assert out["risk_allowed"] is False

    def test_passes_through_when_allowed(self):
        signals = pd.Series([1, -1, 0])
        out = risk_filter(signals, allow_trading=True)
        assert list(out["signals"]) == [1, -1, 0]
        assert out["trading_enabled"] is True


class TestRiskExecutionIntegration:
    def test_risk_then_execution(self, capsys):
        df_ohlcv = _mini_ohlcv(80)
        raw = generate_signals(build_dataset(df_ohlcv))["signal"]

        daily = check_daily_loss_limit(current_pnl=-50.0, daily_loss_limit=-150.0)
        dd = check_max_drawdown(current_drawdown=-0.04, max_drawdown_limit=-0.10)
        allow = daily["risk_allowed"] and dd["risk_allowed"]

        sizing = calculate_position_size(
            capital=100_000.0,
            risk_per_trade=0.01,
            stop_loss_pct=0.01,
        )
        filtered = risk_filter(raw, allow_trading=allow)

        exec_df, metrics = simulate_execution(
            filtered["signals"],
            initial_capital=100_000.0,
            position_size=sizing["position_size"],
        )

        assert len(exec_df) == len(raw)
        assert metrics["num_orders"] >= 0
        assert filtered["risk_allowed"] is True

        print(f"position_size: {sizing['position_size']:.4f}")
        print("RISK ENGINE V1 OK")

        captured = capsys.readouterr()
        assert "RISK ENGINE V1 OK" in captured.out


def _mini_ohlcv(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2024-06-01", periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.3, n))
    fechamento = price.astype(np.float32)
    return pd.DataFrame(
        {
            "abertura": fechamento,
            "alta": fechamento + 1,
            "baixa": fechamento - 1,
            "fechamento": fechamento,
            "volume": rng.integers(100, 500, n).astype(np.float32),
        },
        index=idx,
    )
