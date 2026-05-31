"""
tests/test_simplification_consolidation.py — simplification, invariants, ci_optimizer, consolidation.
"""

from __future__ import annotations

import os

import pytest

from scripts.run_architecture_gate import LEGACY_PIPELINE_STEPS, PIPELINE_STEPS, run_architecture_gate
from src.ci_optimizer import CISimplifier, GateAnalyzer, PipelineOptimizer
from src.consolidation import FinalValidation, SystemConsolidator, run_consolidation_gate
from src.invariants import (
    InvariantRegistry,
    InvariantValidator,
    bootstrap_system_invariants,
    run_invariant_enforcement,
)
from src.release.mode_manager import ModeManager
from src.simplification import ComplexityReducer, DependencyMap, SystemSurface


@pytest.fixture(autouse=True)
def _reset_mode():
    ModeManager.reset()
    yield
    ModeManager.reset()


class TestDependencyMap:
    def test_no_circular_dependencies(self):
        report = DependencyMap().detect_circular_dependencies()
        assert report["circular"] is False

    def test_unidirectional_layers(self):
        report = DependencyMap().validate_unidirectional()
        assert report["status"] == "PASS", report["failures"]


class TestSystemSurface:
    def test_minimal_api_surface(self):
        surface = SystemSurface().expose_minimal_api_surface()
        assert surface["public_api_count"] >= 10
        assert surface["internal_prefix_count"] >= 1


class TestComplexityReducer:
    def test_complexity_score(self):
        score = ComplexityReducer().compute_system_complexity_score()
        assert score["complexity_score"] >= 20
        assert score["gate_count"] == len(PIPELINE_STEPS)


class TestInvariants:
    def test_bootstrap_invariants(self):
        reg = bootstrap_system_invariants()
        assert reg.validate_invariant_chain()["valid"] is True

    def test_invariant_enforcement_passes(self):
        reports = {g: {"status": "PASS", "failures": []} for g in PIPELINE_STEPS[:3]}
        report = run_invariant_enforcement(gate_reports=reports)
        assert report["status"] == "PASS", report["failures"]


class TestCIOptimizer:
    def test_analyze_pipeline(self):
        analysis = CISimplifier().analyze_ci_pipeline()
        assert analysis["gate_count"] == 17

    def test_propose_optimized_pipeline(self):
        optimizer = PipelineOptimizer()
        optimized = optimizer.propose_optimized_pipeline()
        equiv = optimizer.validate_equivalence(optimizer.original, optimized)
        assert equiv["coverage_preserved"] is True
        assert len(optimized) < len(optimizer.original)


class TestConsolidation:
    def test_consolidation_gate_with_passing_reports(self):
        reports = {g: {"status": "PASS", "failures": []} for g in LEGACY_PIPELINE_STEPS[:12]}
        report = run_consolidation_gate(gate_reports=reports)
        assert report["status"] == "PASS", report["failures"]

    def test_final_validation_zero_drift(self):
        report = FinalValidation().validate_zero_drift_state()
        assert report["status"] == "PASS", report["failures"]


class TestPipelineV4:
    def test_fourteen_gates(self):
        assert len(PIPELINE_STEPS) == 17
        assert PIPELINE_STEPS[-1] == "adversarial-audit-gate"

    def test_full_pipeline_passes(self):
        os.environ["WDO_CI"] = "1"
        reports = run_architecture_gate(snapshot_runs=5)
        for step in PIPELINE_STEPS:
            assert step in reports, f"missing {step}"
            assert reports[step]["status"] == "PASS", reports[step].get("failures")
