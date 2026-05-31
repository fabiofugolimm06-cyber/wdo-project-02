"""
pipeline_optimizer.py — proposta de pipeline otimizado com equivalência de cobertura.
"""

from __future__ import annotations

from typing import Any

from src.ci_optimizer.gate_analyzer import GateAnalyzer
from src.simplification.complexity_reducer import _GATE_LAYERS

# Camadas mínimas cobertas pelo pipeline consolidado v7.
_MINIMUM_COVERAGE_LAYERS: tuple[str, ...] = (
    "contracts",
    "data",
    "evolution",
    "snapshot_spec",
    "observability",
    "system_lock",
    "config",
    "watchdog",
    "prod_lock",
    "failsafe",
)

_LAYER_TO_GATE: dict[str, str] = {
    "contracts": "contract-gate",
    "data": "data-gate",
    "evolution": "evolution-gate",
    "snapshot_spec": "snapshot-spec-gate",
    "observability": "audit-observability-gate",
    "health": "system-health-gate",
    "system_lock": "system-lock-gate",
    "config": "config-freeze-gate",
    "watchdog": "watchdog-stability-gate",
    "prod_lock": "production-lock-gate",
    "failsafe": "failsafe-gate",
    "redundancy_final": "final-consolidation-gate",
}


class PipelineOptimizer:
    """
    Propõe pipeline reduzido mantendo cobertura por camada.

    Pipeline ativo: 12 gates consolidados (cobertura legacy 18).
    """

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.original = pipeline_steps or PIPELINE_STEPS

    def propose_optimized_pipeline(self) -> tuple[str, ...]:
        # Referência teórica — remove gates meta/overlap informativo.
        skip = {"final-consolidation-gate", "system-health-gate"}
        return tuple(g for g in self.original if g not in skip)

    def validate_equivalence(
        self,
        original: tuple[str, ...],
        optimized: tuple[str, ...],
    ) -> dict[str, Any]:
        failures: list[str] = []

        opt_layers = {_GATE_LAYERS.get(g, "unknown") for g in optimized}

        missing_layers = set(_MINIMUM_COVERAGE_LAYERS) - opt_layers
        if missing_layers:
            failures.append(
                f"coverage: camadas ausentes no otimizado: {sorted(missing_layers)}."
            )

        if len(optimized) >= len(original):
            failures.append(
                "optimization: pipeline otimizado deve ter menos gates que original."
            )

        analyzer_orig = GateAnalyzer(original)
        analyzer_opt = GateAnalyzer(optimized)
        if analyzer_opt.compute_gate_cost()["total_cost"] >= analyzer_orig.compute_gate_cost()["total_cost"]:
            failures.append("optimization: custo total deve reduzir.")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "original_count": len(original),
            "optimized_count": len(optimized),
            "optimized_layers": sorted(opt_layers),
            "coverage_preserved": not missing_layers,
        }
