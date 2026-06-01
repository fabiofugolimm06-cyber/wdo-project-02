"""
ci_learning_engine.py — Level 4: self-optimizing CI learning engine.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
HISTORY_LOG = PROJECT_ROOT / "ci_history_log.jsonl"
OPTIMIZATION_STATE = PROJECT_ROOT / "ci_optimization_state.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_history() -> list[dict[str, Any]]:
    if not HISTORY_LOG.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in HISTORY_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


@dataclass
class LearningAdjustments:
    graph_accuracy_score: float = 0.0
    test_selection_precision: float = 0.0
    impact_prediction_error: float = 0.0
    learning_improvement_rate: float = 0.0
    graph_weight_updates: dict[str, float] = field(default_factory=dict)
    test_confidence_updates: dict[str, float] = field(default_factory=dict)
    module_risk_updates: dict[str, float] = field(default_factory=dict)
    failure_hotspots: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


class CILearningEngine:
    """Analisa histórico CI e ajusta pesos do grafo/seleção de testes."""

    def __init__(self, state_path: Path | None = None, history_path: Path | None = None) -> None:
        self.state_path = state_path or OPTIMIZATION_STATE
        self.history_path = history_path or HISTORY_LOG
        self.state: dict[str, Any] = _load_json(
            self.state_path,
            {
                "graph_weights": {},
                "test_confidence_scores": {},
                "module_risk_scores": {},
                "false_positive_rate": 0.0,
                "false_negative_rate": 0.0,
                "last_optimized": "",
            },
        )

    def detect_failure_patterns(self, history: list[dict[str, Any]] | None = None) -> dict[str, float]:
        rows = history if history is not None else _read_history()
        hotspots: Counter[str] = Counter()
        for row in rows:
            if row.get("test_result") != "FAIL":
                continue
            for path in row.get("changed_files", []):
                hotspots[path] += 1
            for test in row.get("tests_run", []):
                hotspots[f"test::{test}"] += 1
        if not hotspots:
            return {}
        max_count = max(hotspots.values())
        return {k: round(v / max_count, 3) for k, v in hotspots.items()}

    def detect_flaky_tests(self, history: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        rows = history if history is not None else _read_history()
        outcomes: dict[str, list[str]] = defaultdict(list)
        for row in rows[-50:]:
            result = row.get("test_result")
            for test in row.get("tests_run", []):
                if result in {"PASS", "FAIL"}:
                    outcomes[test].append(result)

        flaky: list[dict[str, Any]] = []
        for test, series in outcomes.items():
            if len(series) < 2:
                continue
            transitions = sum(1 for i in range(1, len(series)) if series[i] != series[i - 1])
            if transitions >= 2:
                severity = min(1.0, transitions / len(series))
                flaky.append({"test": test, "severity": round(severity, 3), "outcomes": series[-5:]})
        return flaky

    def optimize_graph_weights(self, history: list[dict[str, Any]] | None = None) -> dict[str, float]:
        rows = history if history is not None else _read_history()
        weights: dict[str, float] = dict(self.state.get("graph_weights", {}))

        for row in rows[-30:]:
            predicted = set(row.get("tests_run", []))
            failed = set(row.get("tests_failed", []))
            passed = set(row.get("tests_passed", []))
            for test in predicted:
                key = f"edge::{test}"
                current = weights.get(key, 1.0)
                if test in failed:
                    weights[key] = round(min(3.0, current + 0.15), 3)
                elif test in passed:
                    weights[key] = round(max(0.5, current - 0.05), 3)

        self.state["graph_weights"] = weights
        return weights

    def optimize_test_confidence(self, history: list[dict[str, Any]] | None = None) -> dict[str, float]:
        rows = history if history is not None else _read_history()
        scores: dict[str, float] = dict(self.state.get("test_confidence_scores", {}))
        flaky = {item["test"] for item in self.detect_flaky_tests(rows)}

        for row in rows[-30:]:
            result = row.get("test_result")
            for test in row.get("tests_run", []):
                current = scores.get(test, 0.75)
                if test in flaky:
                    scores[test] = round(max(0.2, current - 0.2), 3)
                elif result == "PASS":
                    scores[test] = round(min(1.0, current + 0.05), 3)
                elif result == "FAIL":
                    scores[test] = round(max(0.1, current - 0.1), 3)

        self.state["test_confidence_scores"] = scores
        return scores

    def compute_prediction_error(self, history: list[dict[str, Any]] | None = None) -> tuple[float, float]:
        rows = history if history is not None else _read_history()
        false_positives = 0
        false_negatives = 0
        total = max(1, len(rows[-20:]))

        for row in rows[-20:]:
            if row.get("engine_level") == "FULL":
                false_positives += 1
            if row.get("test_result") == "FAIL" and row.get("engine_level") in {"L2", "L3"}:
                false_negatives += 1

        fp_rate = round(false_positives / total, 3)
        fn_rate = round(false_negatives / total, 3)
        self.state["false_positive_rate"] = fp_rate
        self.state["false_negative_rate"] = fn_rate
        return fp_rate, fn_rate

    def apply_feedback(self, execution: dict[str, Any]) -> LearningAdjustments:
        history = _read_history() + [execution]
        fp_rate, fn_rate = self.compute_prediction_error(history)
        graph_weights = self.optimize_graph_weights(history)
        test_confidence = self.optimize_test_confidence(history)
        hotspots = self.detect_failure_patterns(history)

        recommendations: list[str] = []
        if fp_rate > 0.35:
            recommendations.append("reduce_bfs_scope")
            for key in list(graph_weights.keys()):
                graph_weights[key] = round(max(0.5, graph_weights[key] - 0.1), 3)
        if fn_rate > 0.25:
            recommendations.append("expand_impact_graph")
            for key in list(graph_weights.keys()):
                graph_weights[key] = round(min(3.0, graph_weights[key] + 0.1), 3)

        module_risk = dict(self.state.get("module_risk_scores", {}))
        for path, score in hotspots.items():
            if path.startswith("test::"):
                continue
            module_risk[path] = round(min(1.0, module_risk.get(path, 0.0) + score * 0.2), 3)

        self.state["graph_weights"] = graph_weights
        self.state["test_confidence_scores"] = test_confidence
        self.state["module_risk_scores"] = module_risk
        self.state["last_optimized"] = _utc_now()
        _save_json(self.state_path, self.state)

        prev_fp = execution.get("previous_false_positive_rate", fp_rate)
        improvement = round(max(0.0, prev_fp - fp_rate), 3)

        return LearningAdjustments(
            graph_accuracy_score=round(max(0.0, 1.0 - (fp_rate + fn_rate) / 2), 3),
            test_selection_precision=round(
                sum(test_confidence.values()) / max(1, len(test_confidence)), 3
            ),
            impact_prediction_error=round((fp_rate + fn_rate) / 2, 3),
            learning_improvement_rate=improvement,
            graph_weight_updates=graph_weights,
            test_confidence_updates=test_confidence,
            module_risk_updates=module_risk,
            failure_hotspots=hotspots,
            recommendations=recommendations,
        )

    def weighted_test_boost(self, tests: list[str]) -> list[str]:
        scores = self.state.get("test_confidence_scores", {})
        return sorted(tests, key=lambda t: scores.get(t, 0.75), reverse=True)

    def expand_selection_for_flaky(self, tests: list[str], history: list[dict[str, Any]] | None = None) -> list[str]:
        flaky = {item["test"] for item in self.detect_flaky_tests(history)}
        if not flaky:
            return tests
        expanded = list(dict.fromkeys(tests + sorted(flaky)))
        return expanded
