"""
runtime_enforcer.py — enforcement de budget CI e runtime-budget-gate.
"""

from __future__ import annotations

from typing import Any

from src.ci_optimizer.ci_cost_analyzer import CICostAnalyzer
from src.runtime_budget.budget_config import BudgetConfig, DEFAULT_BUDGET
from src.runtime_budget.execution_caps import ExecutionCaps


class RuntimeEnforcer:
    """Garante CI previsível — gate fora do budget = FAIL."""

    def __init__(self, budget: BudgetConfig | None = None) -> None:
        self.budget = budget or DEFAULT_BUDGET
        self._metrics: dict[str, Any] = {}

    def track_runtime_metrics(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        analyzer = CICostAnalyzer()
        timing = analyzer.measure_gate_execution_time()
        caps = ExecutionCaps(self.budget).limit_resource_spikes()

        executed = sorted(gate_reports.keys()) if gate_reports else []
        executed_ms = sum(
            timing["gate_timings_ms"].get(g, 0) for g in executed
        )

        self._metrics = {
            "total_synthetic_ms": timing["total_ms"],
            "executed_synthetic_ms": executed_ms,
            "gate_timings_ms": timing["gate_timings_ms"],
            "executed_gates": executed,
            "resource_caps": caps,
        }
        return dict(self._metrics)

    def enforce_ci_time_budget(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        metrics = self.track_runtime_metrics(gate_reports=gate_reports)
        failures: list[str] = []

        total_ms = metrics["executed_synthetic_ms"] or metrics["total_synthetic_ms"]
        if total_ms > self.budget.max_total_ci_time:
            failures.append(
                f"budget: total {total_ms}ms > max {self.budget.max_total_ci_time}ms."
            )

        for gate, ms in sorted(metrics["gate_timings_ms"].items()):
            if gate_reports and gate not in gate_reports:
                continue
            if ms > self.budget.max_gate_time:
                failures.append(
                    f"budget:{gate}: {ms}ms > max {self.budget.max_gate_time}ms."
                )

        caps = ExecutionCaps(self.budget).limit_resource_spikes()
        failures.extend(caps["failures"])

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "metrics": metrics,
            "budget": self.budget.to_dict(),
        }

    def abort_if_budget_exceeded(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        report = self.enforce_ci_time_budget(gate_reports=gate_reports)
        if report["status"] == "FAIL":
            report["aborted"] = True
        else:
            report["aborted"] = False
        return report


def run_runtime_budget_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate CI — runtime-budget-gate (passo 15)."""
    if gate_reports is None:
        gate_reports = {}

    enforcer = RuntimeEnforcer()
    report = enforcer.abort_if_budget_exceeded(gate_reports=gate_reports)

    return {
        "status": report["status"],
        "failures": report["failures"],
        "budget_metrics": report["metrics"],
        "budget": report["budget"],
        "aborted": report["aborted"],
    }
