"""
tests/test_production_safety_gates.py — runtime budget, safe mode, monitor, failsafe.
"""

from __future__ import annotations

import os

import pytest

from scripts.run_architecture_gate import LEGACY_PIPELINE_STEPS, PIPELINE_STEPS, run_architecture_gate
from src.failsafe import FailsafeEngine, RecoveryStrategy, RollbackController, run_failsafe_gate
from src.release.mode_manager import ModeManager
from src.runtime_budget import BudgetConfig, RuntimeEnforcer, run_runtime_budget_gate
from src.runtime_monitor import AnomalyDetector, LivePipelineMonitor, run_runtime_monitor_gate
from src.safe_mode import (
    DegradedMode,
    EmergencyStop,
    SafeModeController,
    SystemMode,
    run_safe_mode_gate,
)


@pytest.fixture(autouse=True)
def _reset_singletons():
    ModeManager.reset()
    SafeModeController.reset()
    EmergencyStop.reset()
    yield
    ModeManager.reset()
    SafeModeController.reset()
    EmergencyStop.reset()


def _passing_reports(count: int) -> dict:
    return {
        g: {"status": "PASS", "failures": []}
        for g in PIPELINE_STEPS[:count]
    }


class TestRuntimeBudget:
    def test_enforce_ci_time_budget(self):
        report = RuntimeEnforcer().enforce_ci_time_budget(
            gate_reports={
                g: {"status": "PASS", "failures": []}
                for g in LEGACY_PIPELINE_STEPS[:14]
            },
        )
        assert report["status"] == "PASS", report["failures"]

    def test_runtime_budget_gate(self):
        report = run_runtime_budget_gate(
            gate_reports={
                g: {"status": "PASS", "failures": []}
                for g in LEGACY_PIPELINE_STEPS[:14]
            },
        )
        assert report["status"] == "PASS", report["failures"]

    def test_budget_config_defaults(self):
        cfg = BudgetConfig()
        assert cfg.max_cpu_threads >= 1


class TestSafeMode:
    def test_normal_mode_on_passing_pipeline(self):
        report = run_safe_mode_gate(
            gate_reports={
                g: {"status": "PASS", "failures": []}
                for g in LEGACY_PIPELINE_STEPS[:15]
            },
        )
        assert report["status"] == "PASS", report["failures"]
        assert report["system_mode"] == SystemMode.NORMAL.value

    def test_auto_safe_on_instability(self):
        reports = _passing_reports(5)
        reports["data-gate"] = {"status": "FAIL", "failures": ["boom"]}
        controller = SafeModeController()
        mode = controller.auto_escalate_on_instability(failures=["data-gate"])
        assert mode == SystemMode.SAFE

    def test_degraded_mode_scope(self):
        scope = DegradedMode().reduce_ci_scope()
        assert scope["snapshot_runs"] == 5
        assert scope["disabled_gates"]


class TestRuntimeMonitor:
    def test_live_progress(self):
        progress = LivePipelineMonitor().track_live_gate_progress(
            gate_reports=_passing_reports(10),
        )
        assert progress["completed_gates"] == 10

    def test_no_latency_anomalies(self):
        report = AnomalyDetector().detect_gate_latency_anomalies(
            gate_reports={
                g: {"status": "PASS", "failures": []}
                for g in LEGACY_PIPELINE_STEPS[:14]
            },
        )
        assert report["status"] == "PASS", report["failures"]

    def test_runtime_monitor_gate(self):
        report = run_runtime_monitor_gate(
            gate_reports={
                g: {"status": "PASS", "failures": []}
                for g in LEGACY_PIPELINE_STEPS[:16]
            },
        )
        assert report["status"] == "PASS", report["failures"]
        assert report["live_health_score"] >= 50


class TestFailsafe:
    def test_restore_snapshot(self):
        report = RollbackController().restore_snapshot()
        assert report["status"] == "PASS", report["failures"]
        assert report["snapshot_id"]

    def test_recovery_strategy_normal(self):
        strategy = RecoveryStrategy().choose_recovery_strategy(
            gate_reports=_passing_reports(17),
        )
        assert strategy["strategy"] == "none"

    def test_failsafe_gate(self):
        report = run_failsafe_gate(
            gate_reports={
                g: {"status": "PASS", "failures": []}
                for g in LEGACY_PIPELINE_STEPS[:17]
            },
        )
        assert report["status"] == "PASS", report["failures"]
        assert report["fallback_available"] is True

    def test_detect_no_failure(self):
        report = FailsafeEngine().detect_system_failure(
            gate_reports={
                g: {"status": "PASS", "failures": []}
                for g in LEGACY_PIPELINE_STEPS[:17]
            },
        )
        assert report["status"] == "PASS"


class TestPipelineV6:
    def test_twelve_consolidated_gates(self):
        assert len(PIPELINE_STEPS) == 17
        assert len(LEGACY_PIPELINE_STEPS) == 18
        assert PIPELINE_STEPS[-1] == "adversarial-audit-gate"

    def test_full_pipeline_passes(self):
        os.environ["WDO_CI"] = "1"
        reports = run_architecture_gate(snapshot_runs=5)
        for step in PIPELINE_STEPS:
            assert step in reports, f"missing {step}"
            assert reports[step]["status"] == "PASS", reports[step].get("failures")
