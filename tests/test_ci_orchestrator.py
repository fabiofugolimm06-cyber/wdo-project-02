"""Smoke tests for CI Orchestrator and Learning Engine."""

from __future__ import annotations

from ci_learning_engine import CILearningEngine
from ci_orchestrator import compute_change_risk, export_ci_dashboard_metrics


def test_compute_change_risk_low_for_docs():
    risk = compute_change_risk(["docs/pipeline_contracts.md", "PROMPTS.txt"])
    assert risk.risk_level == "LOW"
    assert risk.score < 25


def test_compute_change_risk_high_for_core():
    risk = compute_change_risk(["ast_ci_engine.py", "src/core/engine.py"])
    assert risk.risk_level == "HIGH"
    assert risk.score >= 60


def test_learning_engine_detects_flaky_from_history():
    engine = CILearningEngine()
    history = [
        {"test_result": "PASS", "tests_run": ["tests/test_a.py"]},
        {"test_result": "FAIL", "tests_run": ["tests/test_a.py"]},
        {"test_result": "PASS", "tests_run": ["tests/test_a.py"]},
        {"test_result": "FAIL", "tests_run": ["tests/test_a.py"]},
    ]
    flaky = engine.detect_flaky_tests(history)
    assert any(item["test"] == "tests/test_a.py" for item in flaky)


def test_export_dashboard_metrics():
    metrics = export_ci_dashboard_metrics()
    assert "total_executions" in metrics
    assert "failure_rate" in metrics


def test_call_graph_cache_reuse():
    from ci_cache import build_call_graph_cached, load_cached_call_graph

    files = ["ci_orchestrator.py", "ci_learning_engine.py", "ci_cache.py", "tests/test_ci_orchestrator.py"]
    state1, report1 = build_call_graph_cached(files)
    assert state1.function_count > 0
    assert not report1.reused

    state2, report2 = build_call_graph_cached(files)
    assert report2.reused
    assert state2.function_count == state1.function_count

    loaded, _ = load_cached_call_graph()
    assert loaded is not None
