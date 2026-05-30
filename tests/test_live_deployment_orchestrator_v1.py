"""
Testes do Live Deployment Orchestrator v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.core import run_decision_pipeline
from microstructure.execution_bridge import ExecutionBridge
from microstructure.live import LiveDeploymentOrchestratorV1
from microstructure.production import ProductionSpecV1
from microstructure.risk import RiskGuardianV1
from microstructure.strategy_config import get_default_config


def _ohlcv(n: int = 40, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-11-01 10:00", periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.25, n))
    fechamento = price.astype(np.float32)
    return pd.DataFrame(
        {
            "abertura": fechamento,
            "alta": fechamento + 1,
            "baixa": fechamento - 1,
            "fechamento": fechamento,
            "volume": rng.integers(100, 700, n).astype(np.float32),
        },
        index=idx,
    )


def _build_orchestrator(
    guardian: RiskGuardianV1 | None = None,
    mode: str = "paper",
) -> LiveDeploymentOrchestratorV1:
    cfg = get_default_config("deploy_orch")
    g = guardian or RiskGuardianV1(max_daily_loss=-5000.0, max_drawdown=-0.5)
    bridge_mode = "paper" if mode == "livesim" else mode
    if bridge_mode not in ("paper", "export", "live"):
        bridge_mode = "paper"
    bridge = ExecutionBridge(cfg, mode=bridge_mode)
    spec = ProductionSpecV1(strategy_config=cfg)
    return LiveDeploymentOrchestratorV1(
        decision_engine=run_decision_pipeline,
        risk_guardian=g,
        execution_bridge=bridge,
        production_spec=spec,
        mode=mode,  # type: ignore[arg-type]
        decision_mode="signal_only",
    )


class TestRunStream:
    def test_sequential_without_error(self):
        df = _ohlcv(35)
        out = _build_orchestrator().run_stream(df)
        log = out["log"]
        assert len(log) == len(df)
        assert "signal" in log.columns
        assert "decision" in log.columns
        assert "risk_action" in log.columns
        assert "execution_action" in log.columns

    def test_determinism(self):
        df = _ohlcv(30, seed=99)
        a = _build_orchestrator().run_stream(df)["log"]
        b = _build_orchestrator().run_stream(df)["log"]
        pd.testing.assert_frame_equal(
            a.drop(columns=["execution_action"], errors="ignore"),
            b.drop(columns=["execution_action"], errors="ignore"),
        )

    def test_state_consistent(self):
        df = _ohlcv(25)
        orch = _build_orchestrator()
        orch.run_stream(df)
        state = orch.get_state()
        assert state["mode"] == "paper"
        assert state["status"] == "running"
        assert state["bars_processed"] == len(df)
        assert "risk_state" in state


class TestRiskGuardianBlock:
    def test_blocks_execution(self):
        df = _ohlcv(20)
        guardian = RiskGuardianV1(max_daily_loss=-1.0)
        guardian.force_stop()
        orch = _build_orchestrator(guardian=guardian)
        out = orch.run_stream(df)
        log = out["log"]
        directional = log[log["raw_signal"] != 0]
        if len(directional) > 0:
            assert directional["risk_action"].apply(lambda r: r["blocked"]).all()
            skipped = directional["execution_action"].apply(
                lambda x: isinstance(x, dict) and x.get("status") == "skipped"
            )
            assert skipped.all()
        bridge_log = orch.get_state()["bridge_state"].get("execution_log", [])
        assert all(int(e["signal"]) == 0 for e in bridge_log)


class TestIntegration:
    def test_decision_risk_bridge_pipeline(self):
        df = _ohlcv(32, seed=12)
        orch = _build_orchestrator()
        result = orch.run_stream(df)
        log = result["log"]
        assert set(log["signal"].unique()).issubset({-1, 0, 1})
        bridge_log = result["state"]["bridge_state"]["execution_log"]
        assert len(bridge_log) > 0
        assert log.iloc[0]["production"]["symbol"] == "WDO"

    def test_livesim_mode_events(self):
        df = _ohlcv(18)
        orch = _build_orchestrator(mode="livesim")
        result = orch.run_stream(df)
        events = result["state"]["livesim_events"]
        assert events[0]["type"] == "stream_start"
        assert events[-1]["type"] == "stream_end"
        assert any(e["type"] == "bar" for e in events)

    def test_on_new_market_data_single_bar(self):
        orch = _build_orchestrator()
        bar = {
            "timestamp": "2024-11-01 10:00:00",
            "abertura": 100.0,
            "alta": 101.0,
            "baixa": 99.0,
            "fechamento": 100.5,
            "volume": 500.0,
        }
        entry = orch.on_new_market_data(bar)
        assert "decision" in entry
        assert "risk_action" in entry
        assert entry["signal"] in (-1, 0, 1)


class TestFailSafe:
    def test_halt_on_bad_timestamp_order(self):
        orch = _build_orchestrator()
        bar1 = {
            "timestamp": "2024-11-01 10:01:00",
            "abertura": 100.0,
            "alta": 101.0,
            "baixa": 99.0,
            "fechamento": 100.0,
            "volume": 100.0,
        }
        bar0 = {
            "timestamp": "2024-11-01 10:00:00",
            "abertura": 100.0,
            "alta": 101.0,
            "baixa": 99.0,
            "fechamento": 100.0,
            "volume": 100.0,
        }
        orch.on_new_market_data(bar1)
        orch.on_new_market_data(bar0)
        assert orch.get_state()["status"] == "halted"


class TestLiveDeploymentPipeline:
    def test_full_pipeline(self, capsys):
        df = _ohlcv(28, seed=21)
        orch = _build_orchestrator()
        out = orch.run_stream(df)
        assert not out["log"].empty
        assert out["state"]["bars_processed"] == len(df)

        print("LIVE DEPLOYMENT ORCHESTRATOR V1 OK")
        captured = capsys.readouterr()
        assert "LIVE DEPLOYMENT ORCHESTRATOR V1 OK" in captured.out
