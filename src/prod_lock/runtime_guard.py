"""
runtime_guard.py — guardião de grafo de execução estático.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from src.observability.architecture_trace import ArchitectureTrace


@dataclass
class RuntimeGuard:
    """Detecta mutações runtime vs grafo congelado."""

    _graph_hash: str | None = field(default=None, init=False)
    _frozen_layers: frozenset[str] = field(default_factory=lambda: frozenset({
        "contracts",
        "data",
        "evolution",
        "snapshots",
        "config",
    }))

    def freeze_execution_graph(self) -> str:
        self._graph_hash = self._compute_graph_hash()
        return self._graph_hash

    def _compute_graph_hash(self) -> str:
        trace = ArchitectureTrace()
        graphs = [
            trace.trace_contract_flow("ml_pipeline:v1"),
            trace.trace_data_flow("wdo_ml_snapshot"),
            trace.trace_snapshot_flow("ml_pipeline_v1_seed42"),
        ]
        payload = json.dumps(graphs, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def detect_runtime_mutation(self) -> dict[str, Any]:
        failures: list[str] = []
        if self._graph_hash is None:
            self.freeze_execution_graph()

        current = self._compute_graph_hash()
        if current != self._graph_hash:
            failures.append(
                "runtime: execution graph mutou em runtime "
                f"({self._graph_hash[:12]}… != {current[:12]}…)."
            )

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "graph_hash": current,
        }

    def enforce_static_execution_graph(self) -> dict[str, Any]:
        mutation = self.detect_runtime_mutation()
        failures = list(mutation["failures"])

        for layer in sorted(self._frozen_layers):
            if layer == "config":
                from src.config import run_config_freeze_gate
                report = run_config_freeze_gate()
            elif layer == "contracts":
                from src.ci import ContractCIGate
                report = ContractCIGate().run_full_contract_check()
            elif layer == "data":
                from src.ci import DataCIGate
                report = DataCIGate().run_full_data_check()
            elif layer == "evolution":
                from src.evolution.evolution_registry import validate_evolution_ci
                report = validate_evolution_ci()
            elif layer == "snapshots":
                from src.snapshot_spec import SnapshotCIGate
                report = SnapshotCIGate(snapshot_runs=5).run_full_snapshot_spec_check()
            else:
                continue

            if report["status"] == "FAIL":
                failures.extend(f"{layer}:{m}" for m in report["failures"])

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "graph_hash": mutation.get("graph_hash"),
        }
