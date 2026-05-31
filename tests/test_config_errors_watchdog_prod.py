"""
tests/test_config_errors_watchdog_prod.py — config freeze, errors, watchdog, prod lock.
"""

from __future__ import annotations

import pytest

from scripts.run_architecture_gate import PIPELINE_STEPS
from src.config import (
    ConfigContract,
    ConfigDuplicateError,
    ConfigFreezeEngine,
    ConfigRegistry,
    ConfigValidator,
    bootstrap_production_config_registry,
    build_canonical_config_schema,
    run_config_freeze_gate,
)
from src.errors import ErrorClassifier, ErrorType, FailureRegistry
from src.prod_lock import ProductionLock, RuntimeGuard, run_production_lock_gate
from src.release.mode_manager import ModeManager
from src.watchdog import CIWatchdog, PipelineMonitor, RegressionDetector, run_watchdog_gate


@pytest.fixture(autouse=True)
def _reset_mode():
    ModeManager.reset()
    yield
    ModeManager.reset()


class TestConfigLayer:
    def test_config_registry_append_only(self):
        reg = bootstrap_production_config_registry()
        contract = reg.get_config("wdo_system_config")
        with pytest.raises(ConfigDuplicateError):
            reg.register_config(contract)

    def test_config_freeze_gate_passes(self):
        report = run_config_freeze_gate()
        assert report["status"] == "PASS", report["failures"]

    def test_block_unregistered_v1_overwrite(self):
        engine = ConfigFreezeEngine()
        engine.freeze_active_config()
        schema = build_canonical_config_schema()
        schema["pipeline"] = {**schema["pipeline"], "snapshot_runs": 99}
        proposed = ConfigContract.create(
            config_id="wdo_system_config",
            version="v1",
            schema=schema,
            locked=True,
        )
        report = engine.block_unregistered_changes(proposed)
        assert report["status"] == "FAIL"


class TestErrorTaxonomy:
    def test_classify_contract_violation(self):
        err = ErrorClassifier().classify_error(
            "contract violation detected",
            origin="contract-gate",
        )
        assert err.error_type == ErrorType.CONTRACT_VIOLATION

    def test_failure_registry(self):
        registry = FailureRegistry()
        err = ErrorClassifier().classify_error("data drift", origin="data-gate")
        registry.register_failure(err, gate="data-gate", run_id="run-1")
        assert registry.compute_failure_rate()["total"] == 1


class TestWatchdog:
    def test_pipeline_monitor_success_rate(self):
        monitor = PipelineMonitor()
        monitor.record_run(
            run_id="r1",
            run_hash="abc",
            gate_reports={"contract-gate": {"status": "PASS", "failures": []}},
        )
        stats = monitor.track_run_success_rate()
        assert stats["success_rate"] == 1.0

    def test_regression_detector(self):
        detector = RegressionDetector()
        baseline = {"g1": {"status": "PASS", "failures": []}}
        detector.set_baseline(run_hash="hash1", gate_reports=baseline)
        report = detector.flag_regression(
            run_hash="hash2",
            gate_reports={"g1": {"status": "FAIL", "failures": ["x"]}},
        )
        assert report["status"] == "FAIL"

    def test_watchdog_gate_with_reports(self):
        reports = {
            f"{g}": {"status": "PASS", "failures": []}
            for g in ("contract-gate", "data-gate")
        }
        report = run_watchdog_gate(gate_reports=reports, run_hash="deterministic-hash")
        assert report["status"] == "PASS", report["failures"]


class TestProductionLock:
    def test_runtime_guard_static_graph(self):
        guard = RuntimeGuard()
        guard.freeze_execution_graph()
        assert guard.detect_runtime_mutation()["status"] == "PASS"

    def test_production_lock_gate(self):
        report = run_production_lock_gate()
        assert report["status"] == "PASS", report["failures"]


class TestPipelineV3:
    def test_twelve_gates_defined(self):
        assert len(PIPELINE_STEPS) == 17
        assert PIPELINE_STEPS[-1] == "adversarial-audit-gate"
