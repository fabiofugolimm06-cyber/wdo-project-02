"""
Testes do Reporting & Performance Analytics v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.backtest.engine_v3 import run_backtest_v3
from microstructure.features.datasets import build_dataset
from microstructure.reporting import generate_performance_report
from microstructure.signal.signal_engine import generate_signals


def _ohlcv(n: int = 250, seed: int = 42) -> pd.DataFrame:
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


_REPORT_KEYS = {
    "total_return",
    "annualized_return",
    "sharpe",
    "max_drawdown",
    "calmar_ratio",
    "win_rate",
    "num_trades",
    "avg_trade_return",
    "profit_factor",
}


class TestGeneratePerformanceReport:
    def test_all_metrics_present(self):
        df = _ohlcv()
        sig = generate_signals(build_dataset(df))["signal"]
        bt = run_backtest_v3(df, sig, price_col="fechamento")
        report = generate_performance_report(bt)
        assert set(report.keys()) == _REPORT_KEYS

    def test_runs_without_error(self):
        df = _ohlcv(200)
        sig = generate_signals(build_dataset(df))["signal"]
        bt = run_backtest_v3(df, sig, price_col="fechamento")
        report = generate_performance_report(bt)
        assert isinstance(report["total_return"], float)

    def test_profit_factor_from_trades(self):
        backtest_result = {
            "df": pd.DataFrame({"x": [1, 2, 3]}),
            "trades": [
                {"trade_return": 0.02},
                {"trade_return": -0.01},
                {"trade_return": 0.03},
            ],
            "metrics": {
                "total_return": 0.1,
                "sharpe": 1.0,
                "max_drawdown": -0.05,
                "win_rate": 0.6,
                "avg_trade_return": 0.01,
                "completed_trades": 3,
            },
        }
        report = generate_performance_report(backtest_result)
        # (0.02 + 0.03) / 0.01 = 5.0
        assert report["profit_factor"] == pytest.approx(5.0)

    def test_calmar_ratio_calculated(self):
        backtest_result = {
            "df": pd.DataFrame(index=pd.RangeIndex(252)),
            "trades": [],
            "metrics": {
                "total_return": 0.10,
                "sharpe": 0.5,
                "max_drawdown": -0.05,
                "win_rate": 0.5,
                "avg_trade_return": 0.0,
                "completed_trades": 0,
            },
        }
        report = generate_performance_report(backtest_result)
        assert report["annualized_return"] == pytest.approx(0.10, rel=1e-6)
        assert report["calmar_ratio"] == pytest.approx(2.0, rel=1e-6)

    def test_invalid_input_raises(self):
        with pytest.raises(ValueError, match="metrics"):
            generate_performance_report({})


class TestReportingIntegration:
    def test_backtest_v3_integration(self, capsys):
        df = _ohlcv(300)
        sig = generate_signals(build_dataset(df))["signal"]
        bt = run_backtest_v3(df, sig, price_col="fechamento")
        report = generate_performance_report(bt)

        assert report["num_trades"] >= 0
        assert report["profit_factor"] >= 0
        print(f"calmar: {report['calmar_ratio']:.4f}, pf: {report['profit_factor']:.4f}")
        print("REPORTING V1 OK")

        captured = capsys.readouterr()
        assert "REPORTING V1 OK" in captured.out
