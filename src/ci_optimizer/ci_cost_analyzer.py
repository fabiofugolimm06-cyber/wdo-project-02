"""
ci_cost_analyzer.py — análise determinística de custo estrutural do pipeline CI.
"""

from __future__ import annotations

from typing import Any

from src.ci_optimizer.gate_analyzer import GateAnalyzer

# Tempo sintético por unidade de custo (ms) — determinístico, sem wall-clock real.
_MS_PER_COST_UNIT = 100


class CICostAnalyzer:
    """Mede custo relativo de gates sem alterar lógica de execução."""

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS
        self._analyzer = GateAnalyzer(self.pipeline_steps)

    def measure_gate_execution_time(self) -> dict[str, Any]:
        cost_report = self._analyzer.compute_gate_cost()
        timings: dict[str, int] = {}
        for gate, cost in sorted(cost_report["gate_costs"].items()):
            timings[gate] = cost * _MS_PER_COST_UNIT
        return {
            "gate_timings_ms": timings,
            "total_ms": sum(timings.values()),
            "unit": "synthetic_ms",
        }

    def compute_total_pipeline_cost(self) -> dict[str, Any]:
        cost = self._analyzer.compute_gate_cost()
        timing = self.measure_gate_execution_time()
        return {
            "total_cost_units": cost["total_cost"],
            "total_ms": timing["total_ms"],
            "gate_count": len(self.pipeline_steps),
            "gate_costs": cost["gate_costs"],
        }

    def detect_expensive_gates(self, *, threshold_ms: int | None = None) -> dict[str, Any]:
        timings = self.measure_gate_execution_time()["gate_timings_ms"]
        if threshold_ms is None:
            avg = sum(timings.values()) / max(len(timings), 1)
            threshold_ms = int(avg * 1.5)
        expensive = sorted(
            [gate for gate, ms in timings.items() if ms >= threshold_ms],
            key=lambda g: timings[g],
            reverse=True,
        )
        return {
            "threshold_ms": threshold_ms,
            "expensive_gates": expensive,
            "timings_ms": {g: timings[g] for g in expensive},
        }
