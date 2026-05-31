"""
layer_merger.py — proposta de merge seguro entre camadas com equivalência.
"""

from __future__ import annotations

from typing import Any

from src.simplification.complexity_reducer import _GATE_LAYERS
from src.simplification.dependency_map import DependencyMap, LAYER_ORDER
from src.simplification.redundancy_analyzer import RedundancyAnalyzer


class LayerMerger:
    """Consolida lógica duplicada apenas quando equivalência é comprovada."""

    _MERGE_CANDIDATES: tuple[tuple[str, str, str], ...] = (
        ("observability", "audit-enforcement-gate", "observability-fingerprint-gate"),
        ("errors", "error-taxonomy-gate", "watchdog-gate"),
    )

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS

    def propose_safe_layer_merge(self) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        layer_index = {layer: idx for idx, layer in enumerate(LAYER_ORDER)}

        for layer, primary, secondary in self._MERGE_CANDIDATES:
            if primary not in self.pipeline_steps or secondary not in self.pipeline_steps:
                continue
            if _GATE_LAYERS.get(primary) != _GATE_LAYERS.get(secondary):
                continue
            proposals.append(
                {
                    "layer": layer,
                    "merge_into": primary,
                    "absorb": secondary,
                    "layer_order_ok": layer_index.get(layer, 99)
                    >= layer_index.get(_GATE_LAYERS.get(primary, ""), 0),
                    "safe": True,
                }
            )
        return proposals

    def validate_equivalence_before_merge(
        self,
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        failures: list[str] = []

        merge_into = proposal.get("merge_into", "")
        absorb = proposal.get("absorb", "")
        if merge_into not in self.pipeline_steps:
            failures.append(f"merge: gate ausente {merge_into!r}.")
        if absorb not in self.pipeline_steps:
            failures.append(f"merge: gate ausente {absorb!r}.")

        if _GATE_LAYERS.get(merge_into) != _GATE_LAYERS.get(absorb):
            failures.append("merge: gates de camadas distintas — merge bloqueado.")

        functional = RedundancyAnalyzer(self.pipeline_steps).detect_duplicate_validations()
        for dup in functional:
            if merge_into in dup["gates"] or absorb in dup["gates"]:
                failures.append(
                    f"merge: duplicação funcional detectada em {dup['gates']}."
                )

        dep = DependencyMap().validate_unidirectional()
        if dep["status"] == "FAIL":
            failures.append("merge: grafo de dependências inválido pós-merge.")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "proposal": proposal,
            "equivalent": not ordered,
        }
