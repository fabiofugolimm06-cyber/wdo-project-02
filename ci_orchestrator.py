"""
ci_orchestrator.py — CI Orchestrator Levels 1–4.

One command → detect → AST CI (L2/L3) → test → commit → push → metrics → learning.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ast_ci_engine import (
    AST_CI_LEVEL,
    FULL_CI_TARGET,
    PROJECT_ROOT,
    build_call_graph,
    build_graph,
    get_changed_files,
    get_python_files,
    select_tests,
)
from ci_learning_engine import CILearningEngine

METRICS_STORE = PROJECT_ROOT / "ci_metrics_store.json"
HISTORY_LOG = PROJECT_ROOT / "ci_history_log.jsonl"
BATCH_THRESHOLD = int(os.environ.get("CI_BATCH_THRESHOLD", "1"))
SAFE_APPROVED = os.environ.get("SAFE_APPROVED", "").lower() in {"1", "true", "yes"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(title: str, value: Any) -> None:
    print(f"\n=== {title} ===")
    print(value)


def _norm(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _run_git(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _append_history(event: dict[str, Any]) -> None:
    with HISTORY_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


@dataclass
class RiskReport:
    risk_level: str = "LOW"
    score: int = 0
    reason: str = ""


@dataclass
class OrchestratorResult:
    changes_detected: list[str] = field(default_factory=list)
    risk: RiskReport = field(default_factory=RiskReport)
    ci_level: str = "3"
    graph_nodes: int = 0
    graph_edges: int = 0
    call_functions: int = 0
    call_edges: int = 0
    selected_tests: list[str] = field(default_factory=list)
    test_result: str = "SKIP"
    commit_decision: str = "NO"
    push_decision: str = "NO"
    rollback_status: str = "NOT_TRIGGERED"
    pr_status: str = "NOT_CREATED"
    commit_hash: str = ""
    execution_time_ms: int = 0
    learning: dict[str, Any] = field(default_factory=dict)
    exit_code: int = 0


def compute_change_risk(changed_files: list[str]) -> RiskReport:
    """Risk engine — HIGH / MEDIUM / LOW scoring."""
    if not changed_files:
        return RiskReport(risk_level="LOW", score=0, reason="no changes")

    score = 0
    reasons: list[str] = []

    for raw in changed_files:
        path = _norm(raw).lower()
        if any(
            token in path
            for token in (
                "src/core/",
                "ast_ci_engine.py",
                "ast_ci_call_graph.py",
                "validation_engine.py",
            )
        ):
            score += 45
            reasons.append(f"HIGH path: {raw}")
            continue
        if path.startswith("tests/") or "microstructure/" in path or (path.endswith(".py") and path.startswith("ci_")):
            score += 20
            reasons.append(f"MEDIUM path: {raw}")
            continue
        if path.startswith("docs/") or path.endswith(".md") or path == "prompts.txt" or path.startswith("scripts/"):
            score += 5
            reasons.append(f"LOW path: {raw}")
            continue
        if path.endswith(".json") or path.endswith(".jsonl"):
            score += 5
            reasons.append(f"LOW config: {raw}")
            continue
        score += 10
        reasons.append(f"default path: {raw}")

    score = min(100, score)
    if score >= 60:
        level = "HIGH"
    elif score >= 25:
        level = "MEDIUM"
    else:
        level = "LOW"

    return RiskReport(risk_level=level, score=score, reason="; ".join(reasons[:6]))


def rollback_if_failure(*, committed: bool, reason: str) -> str:
    if not committed:
        return "NOT_TRIGGERED"
    result = _run_git(["reset", "--hard", "HEAD~1"])
    if result.returncode == 0:
        _log("ROLLBACK STATUS", f"TRIGGERED — {reason}")
        return f"TRIGGERED — {reason}"
    _log("ROLLBACK STATUS", f"FAILED — {result.stderr.strip()}")
    return f"FAILED — {result.stderr.strip()}"


def _current_branch() -> str:
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else "main"


def _should_delay_commit(metrics: dict[str, Any]) -> bool:
    batch = metrics.get("batch_state", {})
    pending = int(batch.get("pending_runs", 0)) + 1
    batch["pending_runs"] = pending
    batch["last_batch_at"] = _utc_now()
    metrics["batch_state"] = batch
    _save_json(METRICS_STORE, metrics)
    return pending < BATCH_THRESHOLD


def _reset_batch(metrics: dict[str, Any]) -> None:
    metrics["batch_state"] = {"pending_runs": 0, "last_batch_at": _utc_now()}
    _save_json(METRICS_STORE, metrics)


def create_pull_request_if_needed(
    *,
    branch: str,
    risk: RiskReport,
    tests_passed: bool,
    execution: dict[str, Any],
) -> str:
    if branch == "main":
        return "SKIPPED — on main branch"
    if not tests_passed:
        return "SKIPPED — tests failed"
    if risk.risk_level == "HIGH":
        return "SKIPPED — HIGH risk"

    title = "CI ORCHESTRATOR AUTO UPDATE: AST CI impact-based execution"
    body = (
        f"## CI Orchestrator Auto PR\n\n"
        f"- Risk score: {risk.score} ({risk.risk_level})\n"
        f"- CI level: {execution.get('ci_level')}\n"
        f"- Changed files: {len(execution.get('changed_files', []))}\n"
        f"- Tests executed: {len(execution.get('tests_run', []))}\n"
        f"- Execution time: {execution.get('execution_time_ms')} ms\n"
    )
    result = subprocess.run(
        ["gh", "pr", "create", "--title", title, "--body", body],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return f"CREATED — {result.stdout.strip()}"
    return f"FAILED — {result.stderr.strip() or 'gh CLI unavailable'}"


def export_ci_dashboard_metrics() -> dict[str, Any]:
    history = []
    if HISTORY_LOG.exists():
        for line in HISTORY_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    history.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    level_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    failures = 0
    rollbacks = 0
    durations: list[int] = []

    for row in history:
        level_counts[row.get("ci_level", "unknown")] = level_counts.get(row.get("ci_level", "unknown"), 0) + 1
        risk_counts[row.get("risk_level", "unknown")] = risk_counts.get(row.get("risk_level", "unknown"), 0) + 1
        if row.get("test_result") == "FAIL":
            failures += 1
        if row.get("rollback_triggered"):
            rollbacks += 1
        if row.get("execution_time_ms"):
            durations.append(int(row["execution_time_ms"]))

    total = max(1, len(history))
    dashboard = {
        "generated_at": _utc_now(),
        "total_executions": len(history),
        "ci_level_distribution": level_counts,
        "risk_distribution": risk_counts,
        "average_test_time_ms": round(sum(durations) / max(1, len(durations))),
        "failure_rate": round(failures / total, 3),
        "rollback_frequency": round(rollbacks / total, 3),
    }
    export_path = PROJECT_ROOT / "ci_dashboard_metrics.json"
    _save_json(export_path, dashboard)
    return dashboard


def _run_pytest(tests: list[str]) -> tuple[int, list[str], list[str]]:
    if not tests:
        return 0, [], []
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", *tests]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    passed: list[str] = []
    failed: list[str] = []
    if proc.returncode == 0:
        passed = list(tests)
    else:
        failed = list(tests)
    return proc.returncode, passed, failed


def run_orchestrator() -> OrchestratorResult:
    started = time.perf_counter()
    result = OrchestratorResult(ci_level=AST_CI_LEVEL)
    committed = False
    metrics = _load_json(METRICS_STORE, {"executions": [], "batch_state": {"pending_runs": 0}})
    learning_engine = CILearningEngine()

    change_report = get_changed_files()
    result.changes_detected = list(change_report.filtered)
    result.risk = compute_change_risk(result.changes_detected)

    _log("CHANGES DETECTED", len(result.changes_detected))
    for path in result.changes_detected[:20]:
        print(f"  change: {path}")
    _log("RISK SCORE", result.risk.score)
    _log("RISK LEVEL", result.risk.risk_level)
    print(f"  reason: {result.risk.reason}")

    files = get_python_files()
    _graph, reverse_graph, graph_report = build_graph(files)
    call_state = build_call_graph(files)
    result.graph_nodes = graph_report.node_count
    result.graph_edges = graph_report.edge_count
    result.call_functions = call_state.function_count
    result.call_edges = call_state.call_edge_count

    _log("CI LEVEL USED", result.ci_level)
    _log("GRAPH SIZE", f"import nodes={result.graph_nodes} edges={result.graph_edges}")
    _log("CALL GRAPH SIZE", f"functions={result.call_functions} edges={result.call_edges}")

    selection = select_tests(change_report, reverse_graph, call_state)
    selected_tests = list(selection.tests)

    history_rows = []
    if HISTORY_LOG.exists():
        for line in HISTORY_LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    history_rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    flaky = learning_engine.detect_flaky_tests(history_rows)
    if flaky:
        selected_tests = learning_engine.expand_selection_for_flaky(selected_tests, history_rows)
    selected_tests = learning_engine.weighted_test_boost(selected_tests)

    result.selected_tests = selected_tests
    _log("SELECTED TESTS COUNT", len(selected_tests))
    for test in selected_tests[:15]:
        print(f"  test: {test}")
    if len(selected_tests) > 15:
        print(f"  ... (+{len(selected_tests) - 15} more)")

    if not change_report.python_changes:
        result.test_result = "SKIP"
        result.commit_decision = "NO"
        result.push_decision = "NO"
        _log("TEST RESULT", result.test_result)
        _log("COMMIT DECISION", result.commit_decision)
        _log("PUSH DECISION", result.push_decision)
        result.execution_time_ms = int((time.perf_counter() - started) * 1000)
        return result

    if selection.engine_level == "FULL":
        _log("TEST RESULT", "BLOCKED — FULL CI fallback (no auto commit/push)")
        result.test_result = "BLOCKED_FULL_CI"
        result.commit_decision = "NO"
        result.push_decision = "NO"
        result.exit_code = 1
        result.execution_time_ms = int((time.perf_counter() - started) * 1000)
        return result

    exit_code, passed_tests, failed_tests = _run_pytest(selected_tests)
    result.test_result = "PASS" if exit_code == 0 else "FAIL"
    _log("TEST RESULT", result.test_result)

    can_commit = (
        exit_code == 0
        and bool(change_report.python_changes)
        and selection.engine_level != "FULL"
    )

    if not can_commit:
        result.commit_decision = "NO"
        result.push_decision = "NO"
        if exit_code != 0:
            result.rollback_status = rollback_if_failure(
                committed=committed,
                reason="tests failed",
            )
        _log("COMMIT DECISION", result.commit_decision)
        _log("PUSH DECISION", result.push_decision)
        _log("ROLLBACK STATUS", result.rollback_status)
        result.exit_code = exit_code or 1
        result.execution_time_ms = int((time.perf_counter() - started) * 1000)
        return result

    if result.risk.risk_level == "HIGH":
        result.commit_decision = "NO"
        result.push_decision = "NO"
        _log("COMMIT DECISION", "NO — HIGH risk safe mode")
        _log("PUSH DECISION", "NO — HIGH risk safe mode")
    elif result.risk.risk_level == "MEDIUM":
        if _should_delay_commit(metrics):
            result.commit_decision = "DELAYED"
            result.push_decision = "NO"
            _log("COMMIT DECISION", "DELAYED — smart batching")
            _log("PUSH DECISION", "NO")
        else:
            result.commit_decision = "YES"
            result.push_decision = "YES" if SAFE_APPROVED else "NO"
            _log("COMMIT DECISION", result.commit_decision)
            _log("PUSH DECISION", f"{result.push_decision} (SAFE_APPROVED={SAFE_APPROVED})")
    else:
        if _should_delay_commit(metrics):
            result.commit_decision = "DELAYED"
            result.push_decision = "NO"
            _log("COMMIT DECISION", "DELAYED — smart batching")
            _log("PUSH DECISION", "NO")
        else:
            result.commit_decision = "YES"
            result.push_decision = "YES"
            _log("COMMIT DECISION", result.commit_decision)
            _log("PUSH DECISION", result.push_decision)

    if result.commit_decision == "YES":
        add_result = _run_git(["add", "."])
        if add_result.returncode != 0:
            result.commit_decision = "FAILED"
            result.exit_code = add_result.returncode
            _log("COMMIT STATUS", add_result.stderr.strip())
        else:
            commit_msg = (
                "CI ORCHESTRATOR: automated AST CI execution (L3/L2), "
                "tests passed, impacted test suite executed"
            )
            commit_result = _run_git(["commit", "-m", commit_msg])
            if commit_result.returncode != 0:
                result.commit_decision = "FAILED"
                result.exit_code = commit_result.returncode
                _log("COMMIT STATUS", commit_result.stderr.strip() or commit_result.stdout.strip())
            else:
                committed = True
                hash_result = _run_git(["rev-parse", "HEAD"])
                result.commit_hash = hash_result.stdout.strip()
                _log("COMMIT STATUS", f"SUCCESS — {result.commit_hash[:8]}")

                if result.push_decision == "YES":
                    push_result = _run_git(["push", "origin", "HEAD"])
                    if push_result.returncode == 0:
                        _log("PUSH STATUS", "SUCCESS")
                    else:
                        result.push_decision = "FAILED"
                        result.rollback_status = rollback_if_failure(
                            committed=committed,
                            reason="push failed",
                        )
                        result.exit_code = push_result.returncode
                        _log("PUSH STATUS", push_result.stderr.strip())
                else:
                    _log("PUSH STATUS", "SKIPPED by safe mode")

    execution_event = {
        "timestamp": _utc_now(),
        "changed_files": result.changes_detected,
        "python_changes": change_report.python_changes,
        "risk_score": result.risk.score,
        "risk_level": result.risk.risk_level,
        "ci_level": result.ci_level,
        "engine_level": selection.engine_level,
        "tests_run": result.selected_tests,
        "tests_passed": passed_tests,
        "tests_failed": failed_tests,
        "execution_time_ms": int((time.perf_counter() - started) * 1000),
        "commit_hash": result.commit_hash,
        "rollback_triggered": result.rollback_status.startswith("TRIGGERED"),
        "test_result": result.test_result,
        "commit_decision": result.commit_decision,
        "push_decision": result.push_decision,
        "previous_false_positive_rate": learning_engine.state.get("false_positive_rate", 0.0),
    }

    _append_history(execution_event)
    metrics.setdefault("executions", []).append(execution_event)
    _save_json(METRICS_STORE, metrics)
    if result.commit_decision == "YES":
        _reset_batch(metrics)

    adjustments = learning_engine.apply_feedback(execution_event)
    result.learning = {
        "GRAPH_ACCURACY_SCORE": adjustments.graph_accuracy_score,
        "TEST_SELECTION_PRECISION": adjustments.test_selection_precision,
        "IMPACT_PREDICTION_ERROR": adjustments.impact_prediction_error,
        "LEARNING_IMPROVEMENT_RATE": adjustments.learning_improvement_rate,
        "recommendations": adjustments.recommendations,
        "flaky_tests": flaky,
    }
    _log("GRAPH_ACCURACY_SCORE", adjustments.graph_accuracy_score)
    _log("TEST_SELECTION_PRECISION", adjustments.test_selection_precision)
    _log("IMPACT_PREDICTION_ERROR", adjustments.impact_prediction_error)
    _log("LEARNING_IMPROVEMENT_RATE", adjustments.learning_improvement_rate)

    branch = _current_branch()
    result.pr_status = create_pull_request_if_needed(
        branch=branch,
        risk=result.risk,
        tests_passed=result.test_result == "PASS",
        execution=execution_event,
    )
    _log("PR STATUS", result.pr_status)

    dashboard = export_ci_dashboard_metrics()
    _log("DASHBOARD EXPORT", f"ci_dashboard_metrics.json ({dashboard['total_executions']} executions)")

    result.execution_time_ms = int((time.perf_counter() - started) * 1000)
    result.exit_code = exit_code
    return result


def main() -> int:
    print("CI ORCHESTRATOR STARTED (Levels 1–4)")
    outcome = run_orchestrator()
    _log("ORCHESTRATOR EXIT", outcome.exit_code)
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
