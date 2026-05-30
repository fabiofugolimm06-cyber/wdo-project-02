"""
Testes do Risk Guardian System v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.core import run_decision_pipeline
from microstructure.execution_bridge import ExecutionBridge
from microstructure.live import LiveOrchestratorV1
from microstructure.papertrading import PaperTradingEngine
from microstructure.risk import (
    GuardedExecutionBridge,
    GuardedPaperTradingEngine,
    RiskGuardianFilterAdapter,
    RiskGuardianV1,
    apply_guardian_to_decision,
    guarded_run_decision_pipeline,
    state_from_paper,
)
from microstructure.strategy_config import get_default_config


def _timestamps(n: int) -> list[str]:
    idx = pd.date_range("2024-10-01 09:00", periods=n, freq="min")
    return [str(t) for t in idx]


def _ohlcv(n: int = 45, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-10-01 10:00", periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.25, n))
    fechamento = price.astype(np.float32)
    return pd.DataFrame(
        {
            "abertura": fechamento,
            "alta": fechamento + 1,
            "baixa": fechamento - 1,
            "fechamento": fechamento,
            "volume": rng.integers(100, 600, n).astype(np.float32),
        },
        index=idx,
    )


class TestRiskGuardianRules:
    def test_blocks_daily_loss(self):
        g = RiskGuardianV1(max_daily_loss=-100.0)
        out = g.evaluate({"daily_pnl": -150.0}, 1)
        assert out["approved_signal"] == 0
        assert out["blocked"] is True
        assert "daily_loss" in out["reason"]

    def test_blocks_drawdown_halt(self):
        g = RiskGuardianV1(max_drawdown=-0.05)
        out = g.evaluate({"current_drawdown": -0.08}, 1)
        assert out["approved_signal"] == 0
        assert out["halted"] is True
        assert "drawdown" in out["reason"]

    def test_cooldown_after_loss_streak(self):
        g = RiskGuardianV1(max_consecutive_losses=2, cooldown_after_loss=3)
        g.update_state({"pnl": -10.0, "is_loss": True})
        g.update_state({"pnl": -5.0, "is_loss": True})
        assert g.get_state()["cooldown_remaining"] == 3
        out = g.evaluate(None, 1)
        assert out["approved_signal"] == 0
        assert "cooldown" in out["reason"]

    def test_allows_when_safe(self):
        g = RiskGuardianV1()
        out = g.evaluate(
            {"daily_pnl": 50.0, "current_drawdown": -0.01, "exposure": 0.0},
            1,
        )
        assert out["approved_signal"] == 1
        assert out["blocked"] is False
        assert out["reason"] == "approved"

    def test_kill_switch(self):
        g = RiskGuardianV1()
        g.force_stop()
        out = g.evaluate(None, -1)
        assert out["approved_signal"] == 0
        assert "kill_switch" in out["reason"]
        flat = g.evaluate(None, 0)
        assert flat["approved_signal"] == 0

    def test_fail_safe_invalid_signal(self):
        g = RiskGuardianV1()
        out = g.evaluate(None, 99)
        assert out["approved_signal"] == 0
        assert "fail_safe" in out["reason"]

    def test_exposure_blocks(self):
        g = RiskGuardianV1(max_position_exposure=1.0)
        out = g.evaluate(
            {"exposure": 1.0, "position": 1},
            {"signal": 1, "risk": {"position_size": 1.0}},
        )
        assert out["approved_signal"] == 0
        assert "exposure" in out["reason"]


class TestDeterminism:
    def test_same_input_same_output(self):
        g1 = RiskGuardianV1(max_daily_loss=-200.0)
        g2 = RiskGuardianV1(max_daily_loss=-200.0)
        state = {"daily_pnl": -10.0, "current_drawdown": -0.02, "exposure": 0.0}
        a = g1.evaluate(state, 1)
        b = g2.evaluate(state, 1)
        assert a == b


class TestGuardedExecutionBridge:
    def test_blocks_before_bridge(self):
        cfg = get_default_config("guard_bridge")
        inner = ExecutionBridge(cfg, mode="export")
        guardian = RiskGuardianV1(max_daily_loss=-50.0)
        bridge = GuardedExecutionBridge(inner, guardian)
        ts = _timestamps(3)

        entry = bridge.process_signal(1, 100.0, ts[0])
        assert entry["signal"] == 1

        guardian.update_state({"daily_pnl": -60.0})
        entry2 = bridge.process_signal(1, 100.5, ts[1])
        assert entry2["signal"] == 0
        assert entry2["guardian"]["blocked"] is True
        assert entry2["raw_signal_before_guardian"] == 1

    def test_determinism_guarded_bridge(self):
        cfg = get_default_config("guard_det")
        ts = _timestamps(4)
        signals = [0, 1, -1, 0]

        def run():
            g = RiskGuardianV1()
            b = GuardedExecutionBridge(
                ExecutionBridge(cfg, mode="export"), g
            )
            logs = []
            for t, s in zip(ts, signals):
                logs.append(b.process_signal(s, 100.0, t))
            return logs

        assert run() == run()


class TestIntegrations:
    def test_live_orchestrator_adapter(self):
        df = _ohlcv(30, seed=11)
        guardian = RiskGuardianV1(max_daily_loss=-1e9)
        guardian.force_stop()
        adapter = RiskGuardianFilterAdapter(guardian)
        orch = LiveOrchestratorV1(risk_engine=adapter)
        log = orch.run(df, mode="signal_only")["log"]
        assert (log["signal"] == 0).all()

    def test_decision_engine_guard(self):
        df = _ohlcv(40, seed=7)
        raw = run_decision_pipeline(df, mode="signal_only", apply_risk=False)
        guardian = RiskGuardianV1()
        guardian.force_stop()
        blocked = guardian.evaluate(None, 1)
        assert blocked["approved_signal"] == 0
        assert blocked["blocked"] is True

        guarded = apply_guardian_to_decision(guardian, raw)
        last_raw = int(raw["signals"].iloc[-1])
        last_guarded = int(guarded["signals"].iloc[-1])
        if last_raw != 0:
            assert last_guarded == 0
            assert guarded["guardian_last"]["blocked"] is True
        decision = guarded_run_decision_pipeline(guardian, df, mode="signal_only")
        assert "guardian_last" in decision

    def test_apply_guardian_to_decision(self):
        df = _ohlcv(35, seed=9)
        raw = run_decision_pipeline(df, mode="signal_only", apply_risk=False)
        g = RiskGuardianV1(max_daily_loss=-1e6)
        guarded = apply_guardian_to_decision(
            g,
            raw,
            state={"daily_pnl": -500.0, "current_drawdown": -0.2},
        )
        assert "guardian_last" in guarded

    def test_guarded_paper_trading(self):
        cfg = get_default_config("guard_paper")
        paper = PaperTradingEngine(
            initial_capital=100_000.0,
            strategy_config=cfg,
            daily_loss_limit=-5000.0,
        )
        paper.initialize_state()
        guardian = RiskGuardianV1(max_daily_loss=-1e9)
        guarded = GuardedPaperTradingEngine(paper, guardian)
        guarded.update_position(100.0)
        guarded.on_signal(1)
        state = guarded.get_state()
        assert state["position"] in (0, 1)
        assert "guardian" in state


class TestRiskGuardianPipeline:
    def test_full_pipeline(self, capsys):
        g = RiskGuardianV1()
        assert g.evaluate(None, 0)["approved_signal"] == 0
        g.force_stop()
        assert g.evaluate(None, 1)["approved_signal"] == 0
        g.reset()
        assert g.evaluate(None, 1)["approved_signal"] == 1

        print("RISK GUARDIAN V1 OK")
        captured = capsys.readouterr()
        assert "RISK GUARDIAN V1 OK" in captured.out
