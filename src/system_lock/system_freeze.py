"""
system_freeze.py — congela baselines oficiais por camada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from microstructure.contracts.registry import CONTRACT_TYPES, contract_registry
from src.observability.system_fingerprint_logger import SystemFingerprintLogger
from src.system_lock.lock_registry import FreezeRecord, LockRegistry


@dataclass
class SystemFreeze:
    """
    Captura fingerprints congelados por camada.

    Freeze documenta estado oficial; evolução via registry (v2+) continua
    permitida quando registrada no ``LockRegistry`` / Evolution Registry.
    """

    lock_registry: LockRegistry = field(default_factory=LockRegistry)
    _fingerprints: SystemFingerprintLogger = field(
        default_factory=SystemFingerprintLogger,
    )

    def freeze_contracts(self) -> FreezeRecord:
        fp = self._fingerprints.compute_contracts_fingerprint()
        versions = tuple(
            f"{t}:{contract_registry.get_active_version(t)}" for t in CONTRACT_TYPES
        )
        record = FreezeRecord(
            layer="contracts",
            fingerprint=fp,
            active_versions=versions,
        )
        self.lock_registry.register_freeze(record)
        return record

    def freeze_data_layer(self) -> FreezeRecord:
        fp = self._fingerprints.compute_data_fingerprint()
        from src.ci.data_ci_gate import build_canonical_dataset_registry

        registry, _ = build_canonical_dataset_registry()
        versions = tuple(sorted(spec.registry_key for spec in registry.list()))
        record = FreezeRecord(
            layer="data",
            fingerprint=fp,
            active_versions=versions,
        )
        self.lock_registry.register_freeze(record)
        return record

    def freeze_evolution_graph(self) -> FreezeRecord:
        fp = self._fingerprints.compute_evolution_fingerprint()
        from src.evolution.evolution_registry import bootstrap_pipeline_evolution_registry

        evo = bootstrap_pipeline_evolution_registry()
        versions = tuple(
            sv.registry_key
            for contract_type in CONTRACT_TYPES
            for sv in evo.list_versions(contract_type)
        )
        record = FreezeRecord(
            layer="evolution",
            fingerprint=fp,
            active_versions=versions,
        )
        self.lock_registry.register_freeze(record)
        return record

    def freeze_snapshot_specs(self) -> FreezeRecord:
        fp = self._fingerprints.compute_snapshots_fingerprint()
        from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

        snaps = bootstrap_baseline_snapshot_registry()
        versions = tuple(spec.snapshot_id for spec in snaps.list())
        record = FreezeRecord(
            layer="snapshots",
            fingerprint=fp,
            active_versions=versions,
        )
        self.lock_registry.register_freeze(record)
        return record

    def freeze_all(self) -> dict[str, Any]:
        """Congela todas as camadas + fingerprint global."""
        records = {
            "contracts": self.freeze_contracts(),
            "data": self.freeze_data_layer(),
            "evolution": self.freeze_evolution_graph(),
            "snapshots": self.freeze_snapshot_specs(),
        }
        system_fp = self._fingerprints.compute_system_fingerprint()
        self.lock_registry.set_system_fingerprint(system_fp)
        return {
            "layers": {
                name: {
                    "fingerprint": rec.fingerprint,
                    "active_versions": list(rec.active_versions),
                }
                for name, rec in records.items()
            },
            "system_fingerprint": system_fp,
        }
