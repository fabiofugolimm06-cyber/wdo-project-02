"""
redundancy_analyzer.py — detecção de validações duplicadas entre camadas.
"""

from __future__ import annotations

from typing import Any

from src.simplification.complexity_reducer import _GATE_LAYERS, _GATE_OVERLAP
from src.simplification.gate_overlap_detector import GateOverlapDetector


class RedundancyAnalyzer:
    """Mapeia lógica repetida sem quebrar determinismo."""

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS
        self._detector = GateOverlapDetector(self.pipeline_steps)

    def detect_duplicate_validations(self) -> list[dict[str, Any]]:
        duplicates: list[dict[str, Any]] = []
        for item in self._detector.identify_redundant_checks():
            if item["kind"] == "functional":
                duplicates.append(
                    {
                        "gates": (item["gate_a"], item["gate_b"]),
                        "overlap_score": item["overlap_score"],
                        "severity": "critical",
                    }
                )
        return duplicates

    def map_repeated_logic_across_layers(self) -> dict[str, Any]:
        layer_checks: dict[str, list[str]] = {}
        for gate in self.pipeline_steps:
            layer = _GATE_LAYERS.get(gate, "unknown")
            layer_checks.setdefault(layer, []).append(gate)

        cross_layer: list[dict[str, Any]] = []
        for gate, overlaps in sorted(_GATE_OVERLAP.items()):
            if gate not in self.pipeline_steps:
                continue
            gate_layer = _GATE_LAYERS.get(gate, "unknown")
            for upstream in overlaps:
                if upstream not in self.pipeline_steps:
                    continue
                upstream_layer = _GATE_LAYERS.get(upstream, "unknown")
                if upstream_layer != gate_layer:
                    cross_layer.append(
                        {
                            "downstream_gate": gate,
                            "downstream_layer": gate_layer,
                            "upstream_gate": upstream,
                            "upstream_layer": upstream_layer,
                            "relation": "revalidates_upstream",
                        }
                    )

        return {
            "gates_by_layer": {k: v for k, v in sorted(layer_checks.items())},
            "cross_layer_revalidation": cross_layer,
            "functional_duplicates": self.detect_duplicate_validations(),
        }
