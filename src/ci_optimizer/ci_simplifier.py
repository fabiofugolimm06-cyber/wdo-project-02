"""
ci_simplifier.py — análise de pipeline CI e sugestões de consolidação.
"""

from __future__ import annotations

from typing import Any

from src.ci_optimizer.gate_analyzer import GateAnalyzer
from src.simplification.complexity_reducer import ComplexityReducer


class CISimplifier:
    """Detecta gates redundantes e sugere consolidação."""

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS
        self._analyzer = GateAnalyzer(self.pipeline_steps)
        self._reducer = ComplexityReducer(self.pipeline_steps)

    def analyze_ci_pipeline(self) -> dict[str, Any]:
        overlap = self._analyzer.measure_gate_overlap()
        cost = self._analyzer.compute_gate_cost()
        complexity = self._reducer.compute_system_complexity_score()
        return {
            "pipeline_steps": list(self.pipeline_steps),
            "gate_count": len(self.pipeline_steps),
            "overlap": overlap,
            "cost": cost,
            "complexity": complexity,
        }

    def detect_redundant_gates(self) -> list[str]:
        redundant: list[str] = []
        overlap_map = self._analyzer.measure_gate_overlap()["overlap_map"]
        for gate, overlaps in overlap_map.items():
            if len(overlaps) >= 2:
                redundant.append(gate)
        return sorted(redundant)

    def suggest_gate_consolidation(self) -> list[dict[str, Any]]:
        return self._reducer.suggest_gate_consolidation()
