"""
tests/test_production_runtime.py — runtime, API, observability export, deployment, completeness.
"""

from __future__ import annotations

import os

import pytest

from scripts.run_architecture_gate import PIPELINE_STEPS, run_architecture_gate
from src.api import WDOApi
from src.completeness import run_system_completeness_gate
from src.deployment import ReleaseManager, RollbackManager, VersionManager
from src.observability_export import LogStreamer, MetricsExporter, TraceExporter
from src.release.mode_manager import ModeManager
from src.runtime import ExecutionContext, ProductionEngine, RunController
from src.safe_mode import EmergencyStop, SafeModeController


@pytest.fixture(autouse=True)
def _reset_singletons():
    ModeManager.reset()
    RunController.reset()
    VersionManager.reset()
    SafeModeController.reset()
    EmergencyStop.reset()
    yield
    ModeManager.reset()
    RunController.reset()
    VersionManager.reset()
    SafeModeController.reset()
    EmergencyStop.reset()


class TestExecutionContext:
    def test_load_and_bind(self):
        ctx = ExecutionContext()
        ctx.load_environment_config()
        assert ctx.bind_contract_registry() is True
        snap = ctx.initialize_snapshot_state()
        assert snap["snapshot_count"] >= 1


class TestProductionEngine:
    def test_execute_pipeline_without_ci(self):
        os.environ.pop("WDO_CI", None)
        result = ProductionEngine().execute_pipeline(snapshot_runs=3)
        assert result["status"] == "PASS", result.get("failures")
        assert result["fingerprint"]

    def test_run_controller_fingerprint(self):
        ctx = ExecutionContext()
        ctx.load_environment_config()
        ctx.bind_contract_registry()
        ctx.initialize_snapshot_state()
        run = RunController().start_run(ctx)
        assert run["fingerprint"]
        assert len(run["run_id"]) == 16


class TestWDOApi:
    def test_get_latest_snapshot(self):
        report = WDOApi().get_latest_snapshot()
        assert report["status"] == "PASS"
        assert report["snapshot_id"]

    def test_run_pipeline(self):
        os.environ.pop("WDO_CI", None)
        report = WDOApi().run_pipeline(snapshot_runs=3)
        assert report["status"] == "PASS", report.get("failures")


class TestObservabilityExport:
    def test_metrics_exporter(self):
        metrics = MetricsExporter().export_ci_metrics()
        assert metrics["gate_count"] == len(PIPELINE_STEPS)

    def test_trace_exporter(self):
        graph = TraceExporter().export_dependency_graph()
        assert graph["total_edges"] >= 1

    def test_log_streamer(self):
        logs = LogStreamer().stream_structured_logs()
        assert logs[0]["run_hash"]


class TestDeployment:
    def test_version_and_release(self):
        fp = "abc123" * 10 + "abcd"
        deploy = ReleaseManager().deploy_version(version="1.0.0", fingerprint=fp)
        assert deploy["status"] == "PASS"
        promote = ReleaseManager().promote_to_production(version="1.0.0")
        assert promote["status"] == "PASS"

    def test_rollback(self):
        fp = "deadbeef" * 8
        ReleaseManager().deploy_version(version="0.9.0", fingerprint=fp)
        report = RollbackManager().rollback_to_version(version="0.9.0")
        assert report["status"] == "PASS", report.get("failures")


class TestCompletenessGate:
    def test_completeness_gate_passes(self):
        reports = {g: {"status": "PASS", "failures": []} for g in PIPELINE_STEPS[:12]}
        report = run_system_completeness_gate(gate_reports=reports)
        assert report["status"] == "PASS", report["failures"]

    def test_pipeline_v8_thirteen_gates(self):
        assert len(PIPELINE_STEPS) == 17
        assert PIPELINE_STEPS[-1] == "adversarial-audit-gate"

    def test_full_pipeline_passes(self):
        os.environ["WDO_CI"] = "1"
        reports = run_architecture_gate(snapshot_runs=5)
        for step in PIPELINE_STEPS:
            assert step in reports, f"missing {step}"
            assert reports[step]["status"] == "PASS", reports[step].get("failures")
