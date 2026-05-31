"""
lock_registry.py — registry central de freezes e mutações autorizadas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.observability.system_fingerprint_logger import SystemFingerprintLogger


class LockRegistryError(Exception):
    """Erro base do lock registry."""


@dataclass(frozen=True)
class FreezeRecord:
    layer: str
    fingerprint: str
    active_versions: tuple[str, ...] = ()


@dataclass(frozen=True)
class MutationRecord:
    layer: str
    change_type: str
    from_version: str | None
    to_version: str | None
    path: str
    authorized: bool = True


@dataclass(frozen=True)
class ChangeProposal:
    layer: str
    path: str
    change_type: str
    from_version: str | None = None
    to_version: str | None = None
    via_pipeline: bool = False


@dataclass
class LockRegistry:
    """
    Registry append-only de freezes e mutações autorizadas.

    Freeze não impede evolução via registry — mutações autorizadas
    registradas explicitamente.
    """

    _freezes: dict[str, FreezeRecord] = field(default_factory=dict)
    _mutations: list[MutationRecord] = field(default_factory=list)
    _system_fingerprint: str | None = None

    def register_freeze(self, record: FreezeRecord) -> None:
        if record.layer in self._freezes:
            existing = self._freezes[record.layer]
            if existing.fingerprint != record.fingerprint:
                raise LockRegistryError(
                    f"LockRegistry: overwrite de freeze {record.layer!r} proibido."
                )
            return
        self._freezes[record.layer] = record

    def get_freeze(self, layer: str) -> FreezeRecord | None:
        return self._freezes.get(layer)

    def list_frozen_layers(self) -> tuple[str, ...]:
        return tuple(sorted(self._freezes))

    def register_authorized_mutation(self, record: MutationRecord) -> None:
        if not record.authorized:
            raise LockRegistryError(
                "LockRegistry: mutação não autorizada não pode ser registrada."
            )
        self._mutations.append(record)

    def list_mutations(self, layer: str | None = None) -> list[MutationRecord]:
        if layer is None:
            return list(self._mutations)
        return [m for m in self._mutations if m.layer == layer]

    def set_system_fingerprint(self, fingerprint: str) -> None:
        if self._system_fingerprint is None:
            self._system_fingerprint = fingerprint
        elif self._system_fingerprint != fingerprint:
            raise LockRegistryError(
                "LockRegistry: system_fingerprint baseline imutável."
            )

    @property
    def system_fingerprint(self) -> str | None:
        return self._system_fingerprint

    def has_authorized_mutation_for_layer(self, layer: str) -> bool:
        return any(m.layer == layer and m.authorized for m in self._mutations)

    def validate_integrity(self) -> dict[str, Any]:
        errors: list[str] = []
        required = ("contracts", "data", "evolution", "snapshots")
        for layer in required:
            if layer not in self._freezes:
                errors.append(f"freeze ausente: {layer}.")
        if self._system_fingerprint is None:
            errors.append("system_fingerprint baseline ausente.")
        return {
            "valid": len(errors) == 0,
            "frozen_layers": list(self.list_frozen_layers()),
            "errors": sorted(errors),
        }


def bootstrap_production_lock_registry() -> LockRegistry:
    """Bootstrap freeze de produção a partir do estado canônico atual."""
    from src.system_lock.system_freeze import SystemFreeze

    registry = LockRegistry()
    SystemFreeze(lock_registry=registry).freeze_all()
    return registry


def validate_system_lock(registry: LockRegistry | None = None) -> dict[str, Any]:
    """Gate CI — freeze íntegro + sem mutação não autorizada."""
    from src.system_lock.mutation_guard import MutationGuard

    reg = registry or bootstrap_production_lock_registry()
    failures: list[str] = []

    integrity = reg.validate_integrity()
    if not integrity["valid"]:
        failures.extend(integrity["errors"])

    mutation_report = MutationGuard(lock_registry=reg).detect_unauthorized_mutation()
    if mutation_report["status"] == "FAIL":
        failures.extend(mutation_report["failures"])

    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }
