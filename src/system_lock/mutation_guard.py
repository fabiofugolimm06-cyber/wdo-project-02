"""
mutation_guard.py — bloqueio de mutações não autorizadas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.observability.system_fingerprint_logger import SystemFingerprintLogger
from src.system_lock.lock_registry import ChangeProposal, LockRegistry, MutationRecord
from src.system_lock.protected_paths import validate_modification_path


def _ci_report(failures: list[str]) -> dict[str, Any]:
    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }


@dataclass
class MutationGuard:
    """
    Detecta drift vs freeze sem version bump / registro de evolução.

    Writes fora do registry/evolution pipeline → FAIL.
    """

    lock_registry: LockRegistry = field(default_factory=LockRegistry)
    _fingerprints: SystemFingerprintLogger = field(
        default_factory=SystemFingerprintLogger,
    )

    _LAYER_FP_COMPUTE = {
        "contracts": lambda self: self._fingerprints.compute_contracts_fingerprint(),
        "data": lambda self: self._fingerprints.compute_data_fingerprint(),
        "evolution": lambda self: self._fingerprints.compute_evolution_fingerprint(),
        "snapshots": lambda self: self._fingerprints.compute_snapshots_fingerprint(),
    }

    def detect_unauthorized_mutation(self) -> dict[str, Any]:
        failures: list[str] = []

        for layer, compute in self._LAYER_FP_COMPUTE.items():
            frozen = self.lock_registry.get_freeze(layer)
            if frozen is None:
                failures.append(f"{layer}: freeze baseline ausente.")
                continue

            current_fp = compute(self)
            if current_fp == frozen.fingerprint:
                continue

            if self._evolution_allows_drift(layer, frozen, current_fp):
                continue

            if self.lock_registry.has_authorized_mutation_for_layer(layer):
                continue

            failures.append(
                f"{layer}: mutação detectada sem version bump "
                f"(frozen={frozen.fingerprint[:12]}…, "
                f"current={current_fp[:12]}…)."
            )

        system_frozen = self.lock_registry.system_fingerprint
        if system_frozen is not None:
            current_system = self._fingerprints.compute_system_fingerprint()
            if (
                current_system != system_frozen
                and not any(
                    self.lock_registry.has_authorized_mutation_for_layer(layer)
                    for layer in self._LAYER_FP_COMPUTE
                )
            ):
                # só falha se nenhuma camada teve mutação autorizada explícita
                drift_layers = [
                    layer
                    for layer in self._LAYER_FP_COMPUTE
                    if self.lock_registry.get_freeze(layer)
                    and self._LAYER_FP_COMPUTE[layer](self)
                    != self.lock_registry.get_freeze(layer).fingerprint
                ]
                if drift_layers and not all(
                    self.lock_registry.has_authorized_mutation_for_layer(layer)
                    for layer in drift_layers
                ):
                    failures.append(
                        "system: fingerprint global diverge do freeze baseline."
                    )

        return _ci_report(failures)

    def validate_change_against_registry(
        self,
        proposal: ChangeProposal,
    ) -> dict[str, Any]:
        failures: list[str] = []

        path_report = validate_modification_path(
            proposal.path,
            change_type=proposal.change_type,
            via_pipeline=proposal.via_pipeline,
        )
        failures.extend(path_report["failures"])

        if proposal.change_type == "in_place":
            failures.append(
                f"{proposal.layer}: mutação in-place proibida "
                f"(exigir version bump ou registry append)."
            )

        if proposal.change_type == "version_bump":
            if not proposal.to_version or proposal.to_version == proposal.from_version:
                failures.append(
                    f"{proposal.layer}: version_bump exige to_version nova."
                )
            if not proposal.via_pipeline:
                failures.append(
                    f"{proposal.layer}: version_bump deve passar pelo pipeline "
                    f"(evolution/registry)."
                )

        if proposal.change_type == "registry_append" and not proposal.via_pipeline:
            failures.append(
                f"{proposal.layer}: registry_append exige via_pipeline=True."
            )

        frozen = self.lock_registry.get_freeze(proposal.layer)
        if frozen and proposal.change_type == "in_place":
            failures.append(f"{proposal.layer}: camada congelada — in-place bloqueado.")

        return _ci_report(failures)

    def block_unregistered_modifications(
        self,
        proposals: list[ChangeProposal],
    ) -> dict[str, Any]:
        failures: list[str] = []

        for proposal in proposals:
            report = self.validate_change_against_registry(proposal)
            if report["status"] == "FAIL":
                failures.extend(
                    f"{proposal.path}:{msg}" for msg in report["failures"]
                )

        drift = self.detect_unauthorized_mutation()
        if drift["status"] == "FAIL":
            failures.extend(drift["failures"])

        return _ci_report(failures)

    def authorize_mutation(self, proposal: ChangeProposal) -> MutationRecord | None:
        """Registra mutação autorizada após validação."""
        report = self.validate_change_against_registry(proposal)
        if report["status"] == "FAIL":
            return None
        record = MutationRecord(
            layer=proposal.layer,
            change_type=proposal.change_type,
            from_version=proposal.from_version,
            to_version=proposal.to_version,
            path=proposal.path,
            authorized=True,
        )
        self.lock_registry.register_authorized_mutation(record)
        return record

    def _evolution_allows_drift(
        self,
        layer: str,
        frozen: Any,
        current_fp: str,
    ) -> bool:
        """Drift permitido se evolution registry tem cadeia válida pós-freeze."""
        if layer != "evolution" and layer != "contracts":
            return False

        from src.evolution.evolution_registry import bootstrap_pipeline_evolution_registry

        evo = bootstrap_pipeline_evolution_registry()
        current_versions = sorted(
            sv.registry_key
            for contract_type in ("ml_pipeline", "full_pipeline")
            for sv in evo.list_versions(contract_type)
        )
        frozen_versions = list(frozen.active_versions)

        if len(current_versions) > len(frozen_versions):
            report = evo.validate_chain_integrity()
            return report.get("valid", False)

        return False
