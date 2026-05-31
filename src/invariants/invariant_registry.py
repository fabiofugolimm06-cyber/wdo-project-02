"""
invariant_registry.py — registry append-only de invariantes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.invariants.invariant_snapshot import InvariantSnapshot, compute_invariant_set_hash


class InvariantRegistryError(Exception):
    """Erro base do invariant registry."""


class InvariantNotFoundError(InvariantRegistryError):
    """Invariante não encontrado."""


class InvariantDuplicateError(InvariantRegistryError):
    """Overwrite proibido."""


@dataclass(frozen=True)
class InvariantRecord:
    invariant_id: str
    description: str
    layer: str
    rule: str
    hash: str

    @classmethod
    def create(
        cls,
        *,
        invariant_id: str,
        description: str,
        layer: str,
        rule: str,
    ) -> InvariantRecord:
        body = {"invariant_id": invariant_id, "description": description, "layer": layer, "rule": rule}
        return cls(
            invariant_id=invariant_id,
            description=description,
            layer=layer,
            rule=rule,
            hash=compute_invariant_set_hash(body),
        )


@dataclass
class InvariantRegistry:
    """Registry imutável de invariantes (append-only)."""

    _records: dict[str, InvariantRecord] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def register_invariant(self, record: InvariantRecord) -> None:
        if record.invariant_id in self._records:
            raise InvariantDuplicateError(
                f"InvariantRegistry: invariant duplicado {record.invariant_id!r}."
            )
        self._records[record.invariant_id] = record
        self._order.append(record.invariant_id)

    def list_invariants(self) -> list[InvariantRecord]:
        return [self._records[iid] for iid in self._order]

    def get_invariant(self, invariant_id: str) -> InvariantRecord:
        try:
            return self._records[invariant_id]
        except KeyError as exc:
            raise InvariantNotFoundError(
                f"InvariantRegistry: invariant não encontrado {invariant_id!r}."
            ) from exc

    def validate_invariant_chain(self) -> dict[str, Any]:
        errors: list[str] = []
        for iid in self._order:
            record = self._records[iid]
            expected = InvariantRecord.create(
                invariant_id=record.invariant_id,
                description=record.description,
                layer=record.layer,
                rule=record.rule,
            )
            if expected.hash != record.hash:
                errors.append(f"{iid}: hash inconsistente (mutação detectada).")
        return {
            "valid": len(errors) == 0,
            "invariant_count": len(self._records),
            "errors": sorted(errors),
        }

    def build_snapshot(
        self,
        *,
        snapshot_id: str,
        system_state_hash: str,
        validation_results: dict[str, Any],
    ) -> InvariantSnapshot:
        invariant_set = {
            r.invariant_id: {
                "layer": r.layer,
                "rule": r.rule,
                "hash": r.hash,
            }
            for r in self.list_invariants()
        }
        return InvariantSnapshot.build(
            snapshot_id=snapshot_id,
            system_state_hash=system_state_hash,
            invariant_set=invariant_set,
            validation_results=validation_results,
        )


def bootstrap_system_invariants() -> InvariantRegistry:
    registry = InvariantRegistry()
    defaults = (
        ("contracts_immutable", "Contratos frozen salvo version bump", "contracts", "registry_frozen"),
        ("data_deterministic", "Fingerprint OHLCV determinístico", "data", "seed_42_stable"),
        ("snapshots_reproducible", "Snapshot spec reproduzível", "snapshot_spec", "state_hash_stable"),
        ("ci_deterministic", "Pipeline CI determinístico", "ci", "run_hash_stable"),
        ("no_circular_deps", "Dependências unidirecionais", "consolidation", "acyclic_graph"),
        ("config_locked", "Config ativa locked", "config", "freeze_enforced"),
    )
    for iid, desc, layer, rule in defaults:
        registry.register_invariant(
            InvariantRecord.create(
                invariant_id=iid,
                description=desc,
                layer=layer,
                rule=rule,
            )
        )
    return registry
