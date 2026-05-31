"""
snapshot_validator.py — validação de spec, determinismo e registry.
"""

from __future__ import annotations

from typing import Any

from microstructure.contracts import get_contract
from microstructure.contracts.snapshot import (
    build_full_pipeline_snapshot,
    build_ml_pipeline_snapshot,
)
from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from microstructure.model.pipeline import run_ml_pipeline_v1
from microstructure.pipeline.end_to_end import run_full_pipeline
from src.snapshot_spec.snapshot_diff_engine import SnapshotDiffEngine
from src.snapshot_spec.snapshot_registry import SnapshotRegistry
from src.snapshot_spec.snapshot_spec import SnapshotSpec, SnapshotSpecError
from tests.ohlcv_data import make_ohlcv

_ML_BARS = 200
_E2E_BARS = 300


def _ci_failures(failures: list[str]) -> dict[str, Any]:
    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }


class SnapshotValidator:
    """
    Valida ``SnapshotSpec`` como spec oficial do sistema.

    FAIL se seed ausente, determinismo quebrado ou drift vs registry.
    """

    def __init__(
        self,
        *,
        seed: int = WDO_PROJECT_RANDOM_SEED,
        snapshot_runs: int = 20,
    ) -> None:
        self.seed = seed
        self.snapshot_runs = snapshot_runs
        self._diff = SnapshotDiffEngine()

    def validate(self, snapshot: SnapshotSpec) -> dict[str, Any]:
        failures: list[str] = []

        if snapshot.deterministic_seed != self.seed:
            failures.append(
                f"deterministic_seed deve ser {self.seed}, "
                f"got {snapshot.deterministic_seed}."
            )

        try:
            get_contract(snapshot.contract_id)
        except Exception as exc:  # noqa: BLE001
            failures.append(
                f"contract_id {snapshot.contract_id!r} inválido — {exc}."
            )

        if not snapshot.structure.get("schema"):
            failures.append("structure.schema ausente.")
        if not snapshot.structure.get("structure"):
            failures.append("structure.structure ausente.")
        if not snapshot.metrics:
            failures.append("metrics vazio.")

        return _ci_failures(failures)

    def validate_determinism(
        self,
        snapshot: SnapshotSpec,
        *,
        snapshot_runs: int | None = None,
    ) -> dict[str, Any]:
        """``snapshot_runs`` execuções devem produzir spec idêntica."""
        runs = snapshot_runs if snapshot_runs is not None else self.snapshot_runs
        failures: list[str] = []

        if runs < 1:
            failures.append("snapshot_runs deve ser >= 1.")
            return _ci_failures(failures)

        base: SnapshotSpec | None = None
        for run_idx in range(runs):
            set_global_determinism(self.seed)
            current = self.generate_live_spec(snapshot.pipeline_stage)
            if base is None:
                base = current
            else:
                diff = self._diff.diff(base, current)
                if diff["breaking"] or diff["changes"]:
                    for change in diff["changes"]:
                        failures.append(f"run {run_idx + 1}: {change}")

        if base is not None and base.state_hash != snapshot.state_hash:
            failures.append(
                "state_hash live diverge da spec registrada "
                f"({base.state_hash} != {snapshot.state_hash})."
            )

        return _ci_failures(failures)

    def validate_against_registry(
        self,
        snapshot: SnapshotSpec,
        registry: SnapshotRegistry,
    ) -> dict[str, Any]:
        failures: list[str] = []

        integrity = registry.validate_registry_integrity()
        if not integrity["valid"]:
            failures.extend(integrity["errors"])

        try:
            registered = registry.get(snapshot.snapshot_id)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"snapshot_id ausente no registry — {exc}.")
            return _ci_failures(failures)

        if registered.state_hash != snapshot.state_hash:
            failures.append(
                "immutability: state_hash diverge do registry "
                "(overwrite detectado)."
            )

        diff = self._diff.diff(registered, snapshot)
        if diff["changes"]:
            for change in diff["changes"]:
                if change.startswith("state_hash:"):
                    continue
                failures.append(f"registry_drift:{change}")

        return _ci_failures(failures)

    def generate_live_spec(self, pipeline_stage: str) -> SnapshotSpec:
        stage = pipeline_stage.lower()
        if stage == "ml":
            contract = get_contract("ml_pipeline:v1")
            raw = build_ml_pipeline_snapshot(
                run_ml_pipeline_v1(
                    make_ohlcv(_ML_BARS, seed=self.seed),
                    seed=self.seed,
                ),
                contract_id=contract.contract_id,
                contract_version=contract.version,
            )
            snapshot_id = "live_ml"
        elif stage in {"full", "e2e"}:
            contract = get_contract("full_pipeline:v1")
            raw = build_full_pipeline_snapshot(
                run_full_pipeline(
                    make_ohlcv(_E2E_BARS, seed=self.seed),
                    price_col="fechamento",
                ),
                contract_id=contract.contract_id,
                contract_version=contract.version,
            )
            snapshot_id = "live_full"
            stage = "full"
        else:
            raise SnapshotSpecError(f"pipeline_stage desconhecido: {pipeline_stage!r}.")

        return SnapshotSpec.from_raw_snapshot(
            raw,
            snapshot_id=snapshot_id,
            pipeline_stage=stage,
            deterministic_seed=self.seed,
        )
