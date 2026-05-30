"""
Testes do Live Orchestrator v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.core import run_decision_pipeline
from microstructure.execution_bridge import ExecutionBridge
from microstructure.live import LiveOrchestratorV1, RiskFilterAdapter


def _ohlcv(n: int = 50, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-09-01 10:00", periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.3, size=n))
    fechamento = price.astype(np.float32)
    return pd.DataFrame(
        {
            "abertura": fechamento,
            "alta": fechamento + 1,
            "baixa": fechamento - 1,
            "fechamento": fechamento,
            "volume": rng.integers(100, 800, n).astype(np.float32),
        },
        index=idx,
    )


class TestLiveOrchestratorRun:
    def test_runs_without_error(self):
        df = _ohlcv(40)
        orch = LiveOrchestratorV1()
        out = orch.run(df, mode="signal_only")
        assert len(out["log"]) == len(df)
        assert out["final_state"]["total_signals"] == len(df)

    def test_log_not_empty_and_signals_valid(self):
        df = _ohlcv(35)
        log = LiveOrchestratorV1().run(df)["log"]
        assert not log.empty
        assert set(log["signal"].unique()).issubset({-1, 0, 1})

    def test_timestamps_monotonic(self):
        df = _ohlcv(30)
        log = LiveOrchestratorV1().run(df)["log"]
        ts = pd.to_datetime(log["timestamp"])
        assert ts.is_monotonic_increasing

    def test_determinism(self):
        df = _ohlcv(25, seed=88)
        a = LiveOrchestratorV1().run(df)["log"]
        b = LiveOrchestratorV1().run(df)["log"]
        pd.testing.assert_frame_equal(a, b)


class TestNoLookahead:
    def test_future_price_does_not_change_past_signals(self):
        df1 = _ohlcv(45, seed=12)
        df2 = df1.copy()
        df2.loc[df2.index[30:], "fechamento"] = 99999.0

        log1 = LiveOrchestratorV1().run(df1)["log"]
        log2 = LiveOrchestratorV1().run(df2)["log"]

        assert log1["signal"].iloc[:25].tolist() == log2["signal"].iloc[:25].tolist()


class TestIntegrations:
    def test_decision_engine_injection(self):
        df = _ohlcv(20)
        calls: list[int] = []

        def fake_decision(slice_df, mode="signal_only", **kwargs):
            calls.append(len(slice_df))
            return run_decision_pipeline(slice_df, mode=mode, apply_risk=False)

        LiveOrchestratorV1(decision_engine=fake_decision).run(df)
        assert calls == list(range(1, len(df) + 1))

    def test_execution_bridge_compat(self):
        df = _ohlcv(25)
        bridge = ExecutionBridge(mode="export")
        orch = LiveOrchestratorV1(
            risk_engine=RiskFilterAdapter(allow_trading=True),
            execution_bridge=bridge,
        )
        out = orch.run(df, mode="signal_only")
        assert len(bridge.get_state()["execution_log"]) == len(df)
        assert len(out["log"]) == len(df)


class TestLiveOrchestratorPipeline:
    def test_full_pipeline(self, capsys):
        df = _ohlcv(45, seed=7)
        bridge = ExecutionBridge(mode="export")
        orch = LiveOrchestratorV1(execution_bridge=bridge)
        out = orch.run(df, mode="signal_only")

        assert out["final_state"]["longs"] + out["final_state"]["shorts"] + out["final_state"]["flat"] == len(df)
        print(f"bars: {len(out['log'])}, longs: {out['final_state']['longs']}")
        print("LIVE ORCHESTRATOR V1 OK")

        captured = capsys.readouterr()
        assert "LIVE ORCHESTRATOR V1 OK" in captured.out
