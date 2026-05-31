"""
gate_analyzer.py — análise de overlap e custo de gates.
"""

from __future__ import annotations

from typing import Any

from src.simplification.complexity_reducer import _GATE_LAYERS, _GATE_OVERLAP


class GateAnalyzer:
    """Mede sobreposição e custo relativo de gates."""

    _GATE_COST: dict[str, int] = {
        "contract-gate": 2,
        "evolution-gate": 2,
        "data-gate": 2,
        "snapshot-spec-gate": 8,
        "audit-observability-gate": 3,
        "system-health-gate": 10,
        "system-lock-gate": 2,
        "config-freeze-gate": 2,
        "watchdog-stability-gate": 18,
        "production-lock-gate": 6,
        "failsafe-gate": 2,
        "final-consolidation-gate": 2,
        "system-completeness-gate": 2,
        "certification-gate": 3,
        "long-run-validation-gate": 5,
        "release-packaging-gate": 2,
        "adversarial-audit-gate": 2,
    }

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS

    def measure_gate_overlap(self) -> dict[str, Any]:
        overlaps: dict[str, list[str]] = {}
        for gate in self.pipeline_steps:
            if gate in _GATE_OVERLAP:
                active = [g for g in _GATE_OVERLAP[gate] if g in self.pipeline_steps]
                if active:
                    overlaps[gate] = active
        return {
            "overlap_map": overlaps,
            "overlap_count": sum(len(v) for v in overlaps.values()),
        }

    def compute_gate_cost(self) -> dict[str, Any]:
        costs = {
            gate: self._GATE_COST.get(gate, 3) for gate in self.pipeline_steps
        }
        return {
            "gate_costs": costs,
            "total_cost": sum(costs.values()),
            "layers": {gate: _GATE_LAYERS.get(gate, "unknown") for gate in self.pipeline_steps},
        }
