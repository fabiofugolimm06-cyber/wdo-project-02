"""
system_fingerprint_logger.py — fingerprint global determinístico do sistema.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from microstructure.contracts.registry import CONTRACT_TYPES, contract_registry
from src.observability.run_logger import _hash_payload


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass
class SystemFingerprintLogger:
    """
    Agrega fingerprints de contracts, data, snapshots e evolution.

    Totalmente determinístico — mesma configuração → mesmo fingerprint.
    """

    _last_state: dict[str, Any] = field(default_factory=dict, init=False)

    def compute_contracts_fingerprint(self) -> str:
        entries = []
        for key in sorted(contract_registry.list_contracts()):
            contract = contract_registry.get_contract(key)
            entries.append(
                {
                    "registry_key": key,
                    "contract_id": contract.contract_id,
                    "version": contract.version,
                    "required_top_keys": sorted(contract.required_top_keys),
                }
            )
        return _hash_payload({"contracts": entries})

    def compute_data_fingerprint(self) -> str:
        from src.ci.data_ci_gate import build_canonical_dataset_registry

        registry, _ = build_canonical_dataset_registry()
        entries = [
            {
                "registry_key": spec.registry_key,
                "fingerprint": spec.fingerprint,
                "dataset_hash": spec.dataset_hash,
            }
            for spec in sorted(
                registry.list(),
                key=lambda s: s.registry_key,
            )
        ]
        return _hash_payload({"datasets": entries})

    def compute_snapshots_fingerprint(self) -> str:
        from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

        registry = bootstrap_baseline_snapshot_registry()
        entries = [
            {
                "snapshot_id": spec.snapshot_id,
                "state_hash": spec.state_hash,
                "contract_id": spec.contract_id,
            }
            for spec in registry.list()
        ]
        return _hash_payload({"snapshots": entries})

    def compute_evolution_fingerprint(self) -> str:
        from src.evolution.evolution_registry import bootstrap_pipeline_evolution_registry

        registry = bootstrap_pipeline_evolution_registry()
        entries = []
        for contract_type in CONTRACT_TYPES:
            for version in sorted(
                v.version for v in registry.list_versions(contract_type)
            ):
                sv = registry.get_version(contract_type, version)
                entries.append(
                    {
                        "registry_key": sv.registry_key,
                        "hash": sv.hash,
                        "parent_version": sv.parent_version,
                        "status": sv.status.value,
                    }
                )
        return _hash_payload({"evolution": entries})

    def compute_system_fingerprint(self) -> str:
        """SHA256 global sobre todos os subsystems."""
        components = {
            "contracts": self.compute_contracts_fingerprint(),
            "data": self.compute_data_fingerprint(),
            "snapshots": self.compute_snapshots_fingerprint(),
            "evolution": self.compute_evolution_fingerprint(),
        }
        return hashlib.sha256(_canonical_json(components).encode("utf-8")).hexdigest()

    def log_global_state(self) -> dict[str, Any]:
        """Snapshot estruturado do estado global (determinístico)."""
        state = {
            "system_fingerprint": self.compute_system_fingerprint(),
            "components": {
                "contracts": self.compute_contracts_fingerprint(),
                "data": self.compute_data_fingerprint(),
                "snapshots": self.compute_snapshots_fingerprint(),
                "evolution": self.compute_evolution_fingerprint(),
            },
            "derived_timestamp": "2000-01-01T00:00:00Z#system-state",
        }
        self._last_state = state
        return dict(state)

    @property
    def last_state(self) -> dict[str, Any]:
        return dict(self._last_state)
