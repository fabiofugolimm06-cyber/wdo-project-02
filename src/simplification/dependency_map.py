"""
dependency_map.py — grafo de dependências unidirecional entre camadas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LAYER_ORDER: tuple[str, ...] = (
    "contracts",
    "data",
    "evolution",
    "snapshot_spec",
    "config",
    "ci",
    "observability",
    "health",
    "system_lock",
    "errors",
    "watchdog",
    "prod_lock",
    "failsafe",
    "redundancy_final",
    "completeness",
    "certification",
    "long_run",
    "release_packaging",
    "adversarial_audit",
)

_LAYER_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "contracts": (),
    "data": ("contracts",),
    "evolution": ("contracts",),
    "snapshot_spec": ("contracts", "data"),
    "config": ("contracts",),
    "ci": ("contracts", "data", "evolution", "snapshot_spec"),
    "observability": ("contracts", "data", "evolution", "snapshot_spec", "ci"),
    "health": ("contracts", "data", "evolution", "snapshot_spec", "ci"),
    "system_lock": ("contracts", "data", "evolution", "snapshot_spec", "config"),
    "errors": ("ci",),
    "watchdog": ("ci", "observability", "health", "config"),
    "prod_lock": ("system_lock", "config", "ci"),
    "failsafe": ("watchdog", "prod_lock", "observability"),
    "redundancy_final": ("failsafe", "watchdog", "prod_lock"),
    "completeness": ("redundancy_final", "failsafe", "prod_lock"),
    "certification": ("completeness", "failsafe"),
    "long_run": ("certification", "completeness"),
    "release_packaging": ("certification", "long_run"),
    "adversarial_audit": ("release_packaging", "long_run", "certification"),
}


@dataclass
class DependencyMap:
    """Mapa de dependências arquiteturais — camadas unidirecionais."""

    dependencies: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(_LAYER_DEPENDENCIES)
    )

    def build_full_dependency_graph(self) -> dict[str, Any]:
        nodes = [{"id": layer, "order": idx} for idx, layer in enumerate(LAYER_ORDER)]
        edges: list[dict[str, str]] = []
        for layer, deps in sorted(self.dependencies.items()):
            for dep in deps:
                edges.append({"from": dep, "to": layer, "type": "depends_on"})
        return {
            "nodes": nodes,
            "edges": sorted(edges, key=lambda e: (e["from"], e["to"])),
        }

    def detect_circular_dependencies(self) -> dict[str, Any]:
        cycles: list[list[str]] = []
        visited: set[str] = set()
        stack: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> None:
            if node in stack:
                if node in path:
                    start = path.index(node)
                    cycles.append(path[start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            stack.add(node)
            path.append(node)
            for dep in self.dependencies.get(node, ()):
                dfs(dep)
            path.pop()
            stack.remove(node)

        for layer in LAYER_ORDER:
            dfs(layer)

        unique_cycles = sorted({tuple(c) for c in cycles})
        return {
            "circular": bool(unique_cycles),
            "cycles": [list(c) for c in unique_cycles],
            "status": "PASS" if not unique_cycles else "FAIL",
        }

    def compute_layer_coupling(self) -> dict[str, Any]:
        coupling: dict[str, int] = {layer: 0 for layer in LAYER_ORDER}
        for layer, deps in self.dependencies.items():
            coupling[layer] = len(deps)
        total_edges = sum(coupling.values())
        return {
            "coupling_by_layer": coupling,
            "total_edges": total_edges,
            "avg_coupling": total_edges / max(len(LAYER_ORDER), 1),
        }

    def validate_unidirectional(self) -> dict[str, Any]:
        failures: list[str] = []
        layer_index = {layer: idx for idx, layer in enumerate(LAYER_ORDER)}

        for layer, deps in self.dependencies.items():
            idx = layer_index.get(layer, -1)
            for dep in deps:
                dep_idx = layer_index.get(dep, -1)
                if dep_idx >= idx:
                    failures.append(
                        f"layer_order:{dep}→{layer} viola fluxo unidirecional."
                    )

        cycle_report = self.detect_circular_dependencies()
        if cycle_report["circular"]:
            failures.append("circular_dependencies detectadas.")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
        }
