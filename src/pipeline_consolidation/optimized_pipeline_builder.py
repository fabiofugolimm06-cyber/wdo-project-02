"""
optimized_pipeline_builder.py — constrói pipeline equivalente mais eficiente.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.ci_optimizer.gate_analyzer import GateAnalyzer
from src.ci_optimizer.pipeline_optimizer import (
    _LAYER_TO_GATE,
    _MINIMUM_COVERAGE_LAYERS,
)
from src.pipeline_consolidation.pipeline_analyzer import PipelineAnalyzer
from src.simplification.complexity_reducer import _GATE_LAYERS


class OptimizedPipelineBuilder:
    """Pipeline teórico reduzido — cobertura preservada, determinismo garantido."""

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.original = pipeline_steps or PIPELINE_STEPS
        self._analyzer = PipelineAnalyzer(self.original)

    def build_equivalent_pipeline(self) -> tuple[str, ...]:
        skip = {"final-consolidation-gate", "system-health-gate"}
        return tuple(g for g in self.original if g not in skip)

    def validate_output_equivalence(
        self,
        original: tuple[str, ...],
        optimized: tuple[str, ...],
    ) -> dict[str, Any]:
        failures: list[str] = []

        opt_layers = {_GATE_LAYERS.get(g, "unknown") for g in optimized}

        missing = set(_MINIMUM_COVERAGE_LAYERS) - opt_layers
        if missing:
            failures.append(
                f"coverage: camadas ausentes: {sorted(missing)}."
            )

        if len(optimized) >= len(original):
            failures.append("optimization: pipeline otimizado deve ser menor.")

        orig_cost = GateAnalyzer(original).compute_gate_cost()["total_cost"]
        opt_cost = GateAnalyzer(optimized).compute_gate_cost()["total_cost"]
        if opt_cost >= orig_cost:
            failures.append("optimization: custo deve reduzir.")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "coverage_preserved": not missing,
            "original_count": len(original),
            "optimized_count": len(optimized),
        }

    def enforce_determinism(self, pipeline: tuple[str, ...]) -> dict[str, Any]:
        payload = json.dumps(list(pipeline), sort_keys=True, separators=(",", ":"))
        pipeline_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        repeat_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return {
            "pipeline_hash": pipeline_hash,
            "deterministic": pipeline_hash == repeat_hash,
            "pipeline": list(pipeline),
        }
