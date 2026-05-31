"""
snapshot_registry.py — registry append-only de SnapshotSpec.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from microstructure.contracts.snapshot import load_snapshot
from microstructure.determinism import WDO_PROJECT_RANDOM_SEED
from src.snapshot_spec.snapshot_spec import SnapshotSpec

_BASELINE_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "snapshots"
)

_BASELINE_SPECS: tuple[tuple[str, str, str, int], ...] = (
    ("ml_pipeline_v1_seed42", "ml_pipeline_v1_seed42.json", "ml", 200),
    ("full_pipeline_v1_seed42", "full_pipeline_v1_seed42.json", "full", 300),
)


class SnapshotRegistryError(Exception):
    """Erro base do snapshot registry."""


class SnapshotNotFoundError(SnapshotRegistryError):
    """``snapshot_id`` não encontrado."""


class SnapshotDuplicateError(SnapshotRegistryError):
    """Overwrite ou fingerprint duplicado proibido."""


class SnapshotRegistry:
    """
    Registry central de specs oficiais (append-only).

    Regras
    ------
    - ``snapshot_id`` único globalmente
    - ``state_hash`` único (imutabilidade de conteúdo)
    - sem overwrite
    """

    def __init__(self) -> None:
        self._by_id: dict[str, SnapshotSpec] = {}
        self._by_hash: dict[str, str] = {}
        self._by_contract: dict[str, list[str]] = {}

    def register(self, snapshot: SnapshotSpec) -> None:
        if snapshot.snapshot_id in self._by_id:
            raise SnapshotDuplicateError(
                f"SnapshotRegistry: snapshot_id duplicado {snapshot.snapshot_id!r}."
            )
        if snapshot.state_hash in self._by_hash:
            existing = self._by_hash[snapshot.state_hash]
            raise SnapshotDuplicateError(
                f"SnapshotRegistry: state_hash duplicado "
                f"{snapshot.state_hash!r} (já em {existing!r})."
            )

        self._by_id[snapshot.snapshot_id] = snapshot
        self._by_hash[snapshot.state_hash] = snapshot.snapshot_id
        ids = self._by_contract.setdefault(snapshot.contract_id, [])
        if snapshot.snapshot_id not in ids:
            ids.append(snapshot.snapshot_id)
            ids.sort()

    def get(self, snapshot_id: str) -> SnapshotSpec:
        try:
            return self._by_id[snapshot_id]
        except KeyError as exc:
            raise SnapshotNotFoundError(
                f"SnapshotRegistry: snapshot não encontrado {snapshot_id!r}."
            ) from exc

    def list(self, contract_id: str | None = None) -> list[SnapshotSpec]:
        if contract_id is None:
            return sorted(self._by_id.values(), key=lambda s: s.snapshot_id)
        ids = self._by_contract.get(contract_id, [])
        return [self.get(sid) for sid in ids]

    def validate_registry_integrity(self) -> dict[str, Any]:
        errors: list[str] = []
        hashes: list[str] = []

        for snapshot_id, spec in self._by_id.items():
            hashes.append(spec.state_hash)
            from src.snapshot_spec.snapshot_spec import compute_state_hash

            expected = compute_state_hash(
                contract_id=spec.contract_id,
                pipeline_stage=spec.pipeline_stage,
                structure=spec.structure,
                metrics=spec.metrics,
                deterministic_seed=spec.deterministic_seed,
            )
            if expected != spec.state_hash:
                errors.append(f"{snapshot_id}: state_hash inconsistente.")

        if len(set(hashes)) != len(hashes):
            errors.append("state_hash duplicado detectado.")

        return {
            "valid": len(errors) == 0,
            "snapshot_count": len(self._by_id),
            "errors": sorted(errors),
        }


def bootstrap_baseline_snapshot_registry(
    *,
    seed: int = WDO_PROJECT_RANDOM_SEED,
    baseline_dir: Path | None = None,
) -> SnapshotRegistry:
    """Carrega specs baseline oficiais de ``tests/snapshots``."""
    directory = baseline_dir or _BASELINE_DIR
    registry = SnapshotRegistry()

    for snapshot_id, filename, stage, _bars in _BASELINE_SPECS:
        raw = load_snapshot(directory / filename)
        spec = SnapshotSpec.from_raw_snapshot(
            raw,
            snapshot_id=snapshot_id,
            pipeline_stage=stage,
            deterministic_seed=seed,
        )
        registry.register(spec)

    return registry
