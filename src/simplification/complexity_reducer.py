"""
complexity_reducer.py — análise de redundância e complexidade do sistema.
"""

from __future__ import annotations

from typing import Any

# Sobreposição informativa — pipeline consolidado v7.
_GATE_OVERLAP: dict[str, tuple[str, ...]] = {
    "system-health-gate": (
        "contract-gate",
        "data-gate",
        "evolution-gate",
        "snapshot-spec-gate",
    ),
    "production-lock-gate": (
        "system-lock-gate",
        "config-freeze-gate",
        "snapshot-spec-gate",
    ),
    "audit-observability-gate": ("system-health-gate",),
    "watchdog-stability-gate": (
        "audit-observability-gate",
        "system-health-gate",
        "config-freeze-gate",
    ),
    "failsafe-gate": ("watchdog-stability-gate", "production-lock-gate"),
    "final-consolidation-gate": ("failsafe-gate", "watchdog-stability-gate"),
    "system-completeness-gate": ("final-consolidation-gate", "failsafe-gate"),
    "certification-gate": ("system-completeness-gate",),
    "long-run-validation-gate": ("certification-gate",),
    "release-packaging-gate": ("certification-gate", "long-run-validation-gate"),
    "adversarial-audit-gate": (
        "release-packaging-gate",
        "long-run-validation-gate",
        "certification-gate",
    ),
}

_GATE_LAYERS: dict[str, str] = {
    "contract-gate": "contracts",
    "evolution-gate": "evolution",
    "data-gate": "data",
    "snapshot-spec-gate": "snapshot_spec",
    "audit-observability-gate": "observability",
    "system-health-gate": "health",
    "system-lock-gate": "system_lock",
    "config-freeze-gate": "config",
    "watchdog-stability-gate": "watchdog",
    "production-lock-gate": "prod_lock",
    "failsafe-gate": "failsafe",
    "final-consolidation-gate": "redundancy_final",
    "system-completeness-gate": "completeness",
    "certification-gate": "certification",
    "long-run-validation-gate": "long_run",
    "release-packaging-gate": "release_packaging",
    "adversarial-audit-gate": "adversarial_audit",
}


class ComplexityReducer:
    """Identifica redundância e sugere consolidação (sem remover gates ativos)."""

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS

    def identify_redundant_checks(self) -> list[dict[str, Any]]:
        redundant: list[dict[str, Any]] = []
        for gate, overlaps in sorted(_GATE_OVERLAP.items()):
            if gate not in self.pipeline_steps:
                continue
            active_overlaps = [g for g in overlaps if g in self.pipeline_steps]
            if active_overlaps:
                redundant.append(
                    {
                        "gate": gate,
                        "overlaps_with": active_overlaps,
                        "severity": "informational",
                    }
                )
        return redundant

    def suggest_gate_consolidation(self) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        redundant = self.identify_redundant_checks()
        for item in redundant:
            suggestions.append(
                {
                    "action": "consolidate_overlap",
                    "target_gate": item["gate"],
                    "merge_candidates": item["overlaps_with"],
                    "rationale": "preferir gate downstream com responsabilidade agregada",
                }
            )
        return suggestions

    def compute_system_complexity_score(self) -> dict[str, Any]:
        gate_count = len(self.pipeline_steps)
        redundant = self.identify_redundant_checks()
        overlap_edges = sum(len(r["overlaps_with"]) for r in redundant)

        from src.simplification.dependency_map import DependencyMap

        coupling = DependencyMap().compute_layer_coupling()
        from src.simplification.system_surface import SystemSurface

        surface = SystemSurface().expose_minimal_api_surface()

        penalty = gate_count * 2 + overlap_edges + int(coupling["avg_coupling"] * 3)
        score = max(0, 100 - penalty)

        return {
            "complexity_score": score,
            "gate_count": gate_count,
            "overlap_edges": overlap_edges,
            "public_api_count": surface["public_api_count"],
            "avg_layer_coupling": coupling["avg_coupling"],
            "redundant_checks": redundant,
        }
