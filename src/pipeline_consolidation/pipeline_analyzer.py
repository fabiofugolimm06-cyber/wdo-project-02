"""
pipeline_analyzer.py — análise de dependências e pipeline mínimo válido.
"""

from __future__ import annotations

from typing import Any

from src.simplification.complexity_reducer import _GATE_LAYERS, _GATE_OVERLAP
from src.simplification.dependency_map import DependencyMap


class PipelineAnalyzer:
    """Analisa dependências entre gates CI."""

    _OPTIONAL_GATES: frozenset[str] = frozenset(
        {
            "audit-enforcement-gate",
            "error-taxonomy-gate",
        }
    )

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS

    def analyze_gate_dependencies(self) -> dict[str, Any]:
        deps: dict[str, list[str]] = {}
        for gate in self.pipeline_steps:
            upstream = [g for g in _GATE_OVERLAP.get(gate, ()) if g in self.pipeline_steps]
            deps[gate] = sorted(upstream)

        layer_graph = DependencyMap().build_full_dependency_graph()
        return {
            "gate_dependencies": deps,
            "layer_graph_edges": len(layer_graph["edges"]),
            "gate_layers": {g: _GATE_LAYERS.get(g, "unknown") for g in self.pipeline_steps},
        }

    def detect_non_critical_gates(self) -> list[str]:
        return sorted(
            g for g in self.pipeline_steps if g in self._OPTIONAL_GATES
        )

    def compute_minimal_valid_pipeline(self) -> tuple[str, ...]:
        """Pipeline mínimo — remove gates meta/overlap informativo."""
        optional = {"final-consolidation-gate", "system-health-gate"}
        return tuple(g for g in self.pipeline_steps if g not in optional)
