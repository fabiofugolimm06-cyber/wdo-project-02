"""
tests/test_health_release_pipeline.py — health monitor, release controller, pipeline final.
"""

from __future__ import annotations

import os

import pytest

from scripts.run_architecture_gate import PIPELINE_STEPS, run_architecture_gate
from src.health import ConsistencyChecker, InvariantValidator, SystemHealthMonitor
from src.release import ModeManager, ReleaseController, ReleaseMode


@pytest.fixture(autouse=True)
def _reset_mode():
    ModeManager.reset()
    yield
    ModeManager.reset()


class TestInvariantValidator:
    def test_validate_system_invariants_passes(self):
        report = InvariantValidator().validate_system_invariants()
        assert report["status"] == "PASS", report["failures"]

    def test_enforce_core_rules(self):
        report = InvariantValidator().enforce_core_rules()
        assert report["enforced"] is True


class TestConsistencyChecker:
    def test_cross_layer_validation(self):
        report = ConsistencyChecker().cross_layer_validation()
        assert report["status"] == "PASS", report["failures"]

    def test_detect_cross_layer_drift(self):
        report = ConsistencyChecker().detect_cross_layer_drift()
        assert report["status"] == "PASS"
        assert report["drift_detected"] is False


class TestSystemHealthMonitor:
    def test_run_full_health_check(self):
        report = SystemHealthMonitor(snapshot_runs=5).run_full_health_check()
        assert report["status"] == "PASS", report["failures"]
        assert report["health_score"] == 100
        assert report["healthy"] is True


class TestReleaseController:
    def test_ci_mode_strict(self):
        ctrl = ReleaseController()
        ctrl.set_mode("ci")
        assert ctrl.get_mode() == ReleaseMode.CI
        constraints = ctrl.enforce_mode_constraints(gate_reports={})
        assert constraints["strict"] is True
        assert constraints["mutation_guard"] is True

    def test_dev_mode_permissive(self):
        ctrl = ReleaseController()
        ctrl.set_mode("dev")
        report = ctrl.enforce_mode_constraints(
            gate_reports={"x": {"status": "FAIL", "failures": ["err"]}},
        )
        assert report["status"] == "PASS"
        assert report["verbose_logs"] is True

    def test_prod_mutation_guard(self):
        ctrl = ReleaseController()
        ctrl.set_mode("prod")
        constraints = ctrl.enforce_mode_constraints()
        assert constraints["mutation_guard"] is True


class TestFinalPipeline:
    def test_pipeline_steps_order(self):
        assert len(PIPELINE_STEPS) == 17
        assert PIPELINE_STEPS[0] == "contract-gate"
        assert PIPELINE_STEPS[-1] == "adversarial-audit-gate"

    def test_run_architecture_gate_passes(self):
        os.environ["WDO_CI"] = "1"
        reports = run_architecture_gate(snapshot_runs=5)
        for step in PIPELINE_STEPS:
            assert step in reports, f"missing step {step}"
            assert reports[step]["status"] == "PASS", reports[step].get("failures")
