"""
execution_context.py — contexto de execução production runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionContext:
    """Estado de execução rastreável — independente de CI."""

    environment: dict[str, Any] = field(default_factory=dict)
    contract_registry_bound: bool = False
    snapshot_state: dict[str, Any] = field(default_factory=dict)
    run_fingerprint: str | None = None

    def load_environment_config(self) -> dict[str, Any]:
        self.environment = {
            "pythonpath": os.environ.get("PYTHONPATH", "."),
            "omp_num_threads": os.environ.get("OMP_NUM_THREADS", "1"),
            "release_mode": os.environ.get("WDO_RELEASE_MODE", "prod"),
            "ci_mode": os.environ.get("WDO_CI", "0") == "1",
        }
        return dict(self.environment)

    def bind_contract_registry(self) -> bool:
        from microstructure.contracts.registry import contract_registry

        contracts = contract_registry.list_contracts()
        self.contract_registry_bound = len(contracts) > 0
        self.environment["contract_count"] = len(contracts)
        return self.contract_registry_bound

    def initialize_snapshot_state(self) -> dict[str, Any]:
        from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

        registry = bootstrap_baseline_snapshot_registry()
        snapshots = registry.list()
        self.snapshot_state = {
            "snapshot_count": len(snapshots),
            "baseline_snapshot_id": snapshots[0].snapshot_id if snapshots else None,
            "baseline_state_hash": snapshots[0].state_hash if snapshots else None,
        }
        return dict(self.snapshot_state)

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": dict(self.environment),
            "contract_registry_bound": self.contract_registry_bound,
            "snapshot_state": dict(self.snapshot_state),
            "run_fingerprint": self.run_fingerprint,
        }
