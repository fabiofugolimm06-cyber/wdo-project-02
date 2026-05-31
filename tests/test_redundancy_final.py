"""
tests/test_redundancy_final.py — equivalência pipeline consolidado vs legacy.
"""

from __future__ import annotations

import os

import pytest

from scripts.run_architecture_gate import (
    LEGACY_PIPELINE_STEPS,
    PIPELINE_STEPS,
    run_architecture_gate,
)
from src.redundancy_final import (
    SystemOverlapAnalyzer,
    ValidationEquivalenceEngine,
    run_final_consolidation_gate,
    validate_pipeline_reduction_integrity,
)
from src.release.mode_manager import ModeManager
from src.safe_mode import SafeModeController, EmergencyStop


@pytest.fixture(autouse=True)
def _reset():
    ModeManager.reset()
    SafeModeController.reset()
    EmergencyStop.reset()
    yield
    ModeManager.reset()
    SafeModeController.reset()
    EmergencyStop.reset()


class TestOverlapAnalyzer:
    def test_overlap_matrix(self):
        matrix = SystemOverlapAnalyzer().compute_system_overlap_matrix()
        assert matrix["gate_count"] == len(PIPELINE_STEPS)

    def test_no_functional_duplicates(self):
        assert SystemOverlapAnalyzer().detect_duplicate_validations() == []


class TestEquivalenceEngine:
    def test_behavioral_identity(self):
        reports = {
            g: {"status": "PASS", "failures": []} for g in LEGACY_PIPELINE_STEPS
        }
        report = ValidationEquivalenceEngine().enforce_behavioral_identity(reports)
        assert report["status"] == "PASS", report["failures"]

    def test_pipeline_reduction(self):
        report = validate_pipeline_reduction_integrity(
            legacy_steps=LEGACY_PIPELINE_STEPS,
            consolidated_steps=PIPELINE_STEPS,
        )
        assert report["status"] == "PASS", report["failures"]
        assert report["legacy_gate_count"] == 18
        assert report["consolidated_gate_count"] == 17


class TestFinalConsolidationGate:
    def test_final_gate_with_legacy_pass(self):
        legacy = {g: {"status": "PASS", "failures": []} for g in LEGACY_PIPELINE_STEPS}
        consolidated = {g: {"status": "PASS", "failures": []} for g in PIPELINE_STEPS}
        report = run_final_consolidation_gate(
            consolidated_reports=consolidated,
            legacy_reports=legacy,
        )
        assert report["status"] == "PASS", report["failures"]


class TestPipelineV7:
    def test_twelve_consolidated_gates(self):
        assert len(PIPELINE_STEPS) == 17
        assert len(LEGACY_PIPELINE_STEPS) == 18
        assert PIPELINE_STEPS[4] == "audit-observability-gate"
        assert PIPELINE_STEPS[8] == "watchdog-stability-gate"
        assert PIPELINE_STEPS[-1] == "adversarial-audit-gate"

    def test_full_pipeline_passes(self):
        os.environ["WDO_CI"] = "1"
        reports = run_architecture_gate(snapshot_runs=5)
        for step in PIPELINE_STEPS:
            assert step in reports, f"missing {step}"
            assert reports[step]["status"] == "PASS", reports[step].get("failures")
        legacy = reports.get("legacy-expanded", {})
        assert len(legacy) == len(LEGACY_PIPELINE_STEPS)
