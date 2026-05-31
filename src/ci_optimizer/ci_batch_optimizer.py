"""
ci_batch_optimizer.py — agrupamento paralelo e redução de validações redundantes.
"""

from __future__ import annotations

from typing import Any

from src.simplification.dependency_map import DependencyMap
from src.simplification.complexity_reducer import _GATE_LAYERS, _GATE_OVERLAP


class CIBatchOptimizer:
    """Sugestões estruturais de execução — não altera lógica dos gates."""

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS

    def suggest_parallel_safe_gates(self) -> dict[str, Any]:
        """Gates na mesma camada sem dependência sequencial explícita."""
        layer_groups: dict[str, list[str]] = {}
        for gate in self.pipeline_steps:
            layer = _GATE_LAYERS.get(gate, "unknown")
            layer_groups.setdefault(layer, []).append(gate)

        parallel_groups: list[list[str]] = []
        for layer, gates in sorted(layer_groups.items()):
            if len(gates) > 1:
                parallel_groups.append(sorted(gates))

        # contract + evolution + data são upstream independentes (camadas distintas,
        # sem edge entre si) — candidatos a batch paralelo teórico.
        early = [
            g
            for g in self.pipeline_steps[:3]
            if g in {"contract-gate", "evolution-gate", "data-gate"}
        ]
        return {
            "parallel_groups": parallel_groups,
            "early_independent_batch": sorted(early),
            "layer_groups": {k: v for k, v in sorted(layer_groups.items())},
        }

    def propose_grouping(self) -> list[dict[str, Any]]:
        parallel = self.suggest_parallel_safe_gates()
        groups: list[dict[str, Any]] = []

        if parallel["early_independent_batch"]:
            groups.append(
                {
                    "group_id": "bootstrap",
                    "gates": parallel["early_independent_batch"],
                    "execution": "parallel_safe",
                    "rationale": "camadas upstream sem dependência cruzada",
                }
            )

        sequential_tail = [
            g for g in self.pipeline_steps if g not in parallel["early_independent_batch"]
        ]
        groups.append(
            {
                "group_id": "sequential_tail",
                "gates": sequential_tail,
                "execution": "sequential",
                "rationale": "gates downstream com dependência de estado CI",
            }
        )
        return groups

    def reduce_redundant_validations(self) -> dict[str, Any]:
        """Identifica checks duplicados informativos — não remove gates ativos."""
        skip_if_upstream_pass: list[dict[str, str]] = []
        for gate, overlaps in sorted(_GATE_OVERLAP.items()):
            if gate not in self.pipeline_steps:
                continue
            active = [g for g in overlaps if g in self.pipeline_steps]
            if active:
                skip_if_upstream_pass.append(
                    {
                        "gate": gate,
                        "upstream_coverage": ",".join(active),
                        "action": "defer_to_downstream_only",
                    }
                )

        dep_graph = DependencyMap().build_full_dependency_graph()
        return {
            "redundant_validation_map": skip_if_upstream_pass,
            "dependency_edges": len(dep_graph["edges"]),
            "note": "otimização estrutural apenas — pipeline ativo mantém cobertura completa",
        }
