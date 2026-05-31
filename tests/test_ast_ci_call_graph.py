"""Testes do AST CI Engine Level 3 — call graph real."""

from __future__ import annotations

from ast_ci_call_graph import build_call_graph, propagate_call_impact
from ast_ci_engine import ChangeReport, build_graph, get_python_files, select_tests


def test_call_graph_builds_functions_and_edges():
    state = build_call_graph(get_python_files())
    assert state.function_count > 100
    assert state.call_edge_count > 0
    assert len(state.test_exercised_functions) > 0


def test_pipeline_change_selects_tests_via_l3():
    files = get_python_files()
    _, reverse, _ = build_graph(files)
    call_state = build_call_graph(files)

    change = ChangeReport(python_changes=["microstructure/model/pipeline.py"])
    selection = select_tests(change, reverse, call_state)

    assert selection.engine_level == "L3"
    assert "tests/test_pipeline_regression.py" in selection.tests
    assert selection.call_impact is not None
    assert selection.call_impact.propagation_depth >= 0


def test_unmapped_change_falls_back_to_full_ci_not_heuristic():
    files = get_python_files()
    _, reverse, _ = build_graph(files)
    call_state = build_call_graph(files)

    change = ChangeReport(python_changes=["ci_observer.py"])
    selection = select_tests(change, reverse, call_state)

    assert selection.engine_level == "FULL"
    assert selection.tests == ["tests"]
    assert selection.fallback_reason == "full_ci_explicit_no_mapped_tests"


def test_propagate_call_impact_maps_pipeline_to_regression_test():
    state = build_call_graph(get_python_files())
    impact = propagate_call_impact(["microstructure/model/pipeline.py"], state)

    assert impact.affected_functions
    assert any("run_ml_pipeline_v1" in fn for fn in impact.affected_functions)
    assert "tests/test_pipeline_regression.py" in impact.affected_tests
