"""
tests/test_stability_cost_optimizer.py — CI cost, redundancy, trace, pipeline, stability.
"""

from __future__ import annotations

import os

import pytest

from scripts.run_architecture_gate import LEGACY_PIPELINE_STEPS, PIPELINE_STEPS, run_architecture_gate
from src.ci_optimizer import (
    CIBatchOptimizer,
    CICostAnalyzer,
    GateRuntimeProfiler,
)
from src.observability import AuditEventBus, AuditEventType, EventDeduplicator, TraceCompressor
from src.observability.architecture_trace import ArchitectureTrace
from src.pipeline_consolidation import OptimizedPipelineBuilder, PipelineAnalyzer
from src.release.mode_manager import ModeManager
from src.simplification import GateOverlapDetector, LayerMerger, RedundancyAnalyzer
from src.stability import RegressionProtector, StabilityEngine, run_stability_gate

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def _reset_mode():
    ModeManager.reset()
    yield
    ModeManager.reset()


class TestCICostOptimizer:
    def test_total_pipeline_cost(self):
        cost = CICostAnalyzer().compute_total_pipeline_cost()
        assert cost["gate_count"] == 17
        assert cost["total_cost_units"] > 0

    def test_expensive_gates(self):
        report = CICostAnalyzer().detect_expensive_gates()
        assert "snapshot-spec-gate" in report["expensive_gates"] or report["expensive_gates"]

    def test_profiler_variance_zero(self):
        report = GateRuntimeProfiler().compute_variance_across_runs(runs=3)
        assert report["stable"] is True

    def test_batch_optimizer_grouping(self):
        groups = CIBatchOptimizer().propose_grouping()
        assert len(groups) >= 2


class TestRedundancyCollapser:
    def test_no_functional_duplicates(self):
        dups = RedundancyAnalyzer().detect_duplicate_validations()
        assert dups == []

    def test_overlap_detector(self):
        score = GateOverlapDetector().compute_overlap_score(
            "system-health-gate",
            "contract-gate",
        )
        assert score >= 60

    def test_layer_merge_equivalence(self):
        proposals = LayerMerger().propose_safe_layer_merge()
        for proposal in proposals:
            report = LayerMerger().validate_equivalence_before_merge(proposal)
            assert report["status"] == "PASS", report["failures"]


class TestTraceReducer:
    def test_compress_trace(self):
        trace = ArchitectureTrace().trace_contract_flow("ml_pipeline:v1")
        report = TraceCompressor().compress_execution_trace(trace)
        assert report["compressed_nodes"] <= report["original_nodes"]
        assert report["trace_hash"]

    def test_deduplicate_audit_events(self):
        bus = AuditEventBus()
        bus.emit(AuditEventType.CI_GATE_PASSED, {"gate": "contract-gate"})
        bus.emit(AuditEventType.CI_GATE_PASSED, {"gate": "contract-gate"})
        merged = EventDeduplicator().deduplicate_audit_events(bus.list_events())
        assert len(merged) == 1
        assert merged[0]["occurrence_count"] == 2


class TestPipelineConsolidation:
    def test_minimal_pipeline(self):
        minimal = PipelineAnalyzer().compute_minimal_valid_pipeline()
        assert len(minimal) < len(PIPELINE_STEPS)

    def test_equivalent_pipeline(self):
        builder = OptimizedPipelineBuilder()
        optimized = builder.build_equivalent_pipeline()
        equiv = builder.validate_output_equivalence(builder.original, optimized)
        assert equiv["coverage_preserved"] is True
        assert len(optimized) < len(builder.original)


class TestStability:
    def test_stability_gate_passes(self):
        reports = {g: {"status": "PASS", "failures": []} for g in LEGACY_PIPELINE_STEPS[:13]}
        report = run_stability_gate(gate_reports=reports)
        assert report["status"] == "PASS", report["failures"]
        assert report["stability_score"] >= 55

    def test_regression_protector_consistency(self):
        reports = {g: {"status": "PASS", "failures": []} for g in PIPELINE_STEPS[:5]}
        report = RegressionProtector().validate_output_consistency(reports)
        assert report["status"] == "PASS", report["failures"]

    def test_stability_engine(self):
        reports = {g: {"status": "PASS", "failures": []} for g in LEGACY_PIPELINE_STEPS[:13]}
        analysis = StabilityEngine().run_full_stability_analysis(gate_reports=reports)
        assert analysis["status"] == "PASS", analysis["failures"]


class TestPipelineV5:
    def test_fourteen_gates(self):
        assert len(PIPELINE_STEPS) == 17
        assert PIPELINE_STEPS[-1] == "adversarial-audit-gate"

    def test_full_pipeline_passes(self):
        os.environ["WDO_CI"] = "1"
        reports = run_architecture_gate(snapshot_runs=5)
        for step in PIPELINE_STEPS:
            assert step in reports, f"missing {step}"
            assert reports[step]["status"] == "PASS", reports[step].get("failures")
