"""
gate_overlap_detector.py — score de sobreposição entre pares de gates.
"""

from __future__ import annotations

from typing import Any

from src.simplification.complexity_reducer import _GATE_LAYERS, _GATE_OVERLAP


class GateOverlapDetector:
    """Detecta overlap estrutural entre gates CI."""

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS

    def compute_overlap_score(self, gate_a: str, gate_b: str) -> int:
        """Score 0–100: 0 = sem overlap, 100 = validação idêntica."""
        if gate_a == gate_b:
            return 100

        score = 0
        if gate_a in _GATE_OVERLAP and gate_b in _GATE_OVERLAP[gate_a]:
            score += 60
        if gate_b in _GATE_OVERLAP and gate_a in _GATE_OVERLAP[gate_b]:
            score += 60

        layer_a = _GATE_LAYERS.get(gate_a)
        layer_b = _GATE_LAYERS.get(gate_b)
        if layer_a and layer_a == layer_b:
            score += 40

        return min(score, 100)

    def identify_redundant_checks(self) -> list[dict[str, Any]]:
        redundant: list[dict[str, Any]] = []
        gates = [g for g in self.pipeline_steps]
        for i, gate_a in enumerate(gates):
            for gate_b in gates[i + 1 :]:
                score = self.compute_overlap_score(gate_a, gate_b)
                if score >= 40:
                    kind = "functional" if score >= 80 else "informational"
                    redundant.append(
                        {
                            "gate_a": gate_a,
                            "gate_b": gate_b,
                            "overlap_score": score,
                            "kind": kind,
                        }
                    )
        return sorted(redundant, key=lambda r: (-r["overlap_score"], r["gate_a"]))
