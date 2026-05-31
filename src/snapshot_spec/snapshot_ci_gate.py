"""
snapshot_ci_gate.py — CI gate Snapshot-as-Spec (spec enforcement layer).
"""

from __future__ import annotations

from typing import Any

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED
from src.snapshot_spec.snapshot_diff_engine import SnapshotDiffEngine
from src.snapshot_spec.snapshot_registry import (
    SnapshotRegistry,
    bootstrap_baseline_snapshot_registry,
)
from src.snapshot_spec.snapshot_validator import SnapshotValidator


def _ci_report(failures: list[str]) -> dict[str, Any]:
    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }


class SnapshotCIGate:
    """
    CI gate Snapshot-as-Spec — sistema deve alinhar-se à spec, não o contrário.

    Pipeline
    --------
    1. load snapshots (baseline registry)
    2. validate registry integrity
    3. determinism test (20 runs)
    4. diff against baseline snapshot spec
    5. enforce immutability rules
    """

    def __init__(
        self,
        *,
        seed: int = WDO_PROJECT_RANDOM_SEED,
        snapshot_runs: int = 20,
    ) -> None:
        self.seed = seed
        self.snapshot_runs = snapshot_runs
        self._validator = SnapshotValidator(seed=seed, snapshot_runs=snapshot_runs)
        self._diff = SnapshotDiffEngine()

    def run_full_snapshot_spec_check(
        self,
        registry: SnapshotRegistry | None = None,
    ) -> dict[str, Any]:
        failures: list[str] = []

        # 1. load snapshots
        reg = registry or bootstrap_baseline_snapshot_registry(seed=self.seed)

        # 2. validate registry
        integrity = reg.validate_registry_integrity()
        if not integrity["valid"]:
            failures.extend(f"registry:{e}" for e in integrity["errors"])

        for spec in reg.list():
            # validate spec shape
            validation = self._validator.validate(spec)
            if validation["status"] == "FAIL":
                failures.extend(
                    f"{spec.snapshot_id}:validate:{msg}"
                    for msg in validation["failures"]
                )

            # 3. determinism (20 runs)
            det = self._validator.validate_determinism(
                spec,
                snapshot_runs=self.snapshot_runs,
            )
            if det["status"] == "FAIL":
                failures.extend(
                    f"{spec.snapshot_id}:determinism:{msg}"
                    for msg in det["failures"]
                )

            # 4. diff against baseline (live vs registered spec)
            live = self._validator.generate_live_spec(spec.pipeline_stage)
            diff = self._diff.diff(spec, live)
            if diff["breaking"]:
                failures.extend(
                    f"{spec.snapshot_id}:baseline_diff:{change}"
                    for change in diff["changes"]
                )
            elif diff["changes"]:
                failures.extend(
                    f"{spec.snapshot_id}:metric_drift:{change}"
                    for change in diff["changes"]
                )

            # 5. immutability vs registry
            immutability = self._validator.validate_against_registry(spec, reg)
            if immutability["status"] == "FAIL":
                failures.extend(
                    f"{spec.snapshot_id}:immutability:{msg}"
                    for msg in immutability["failures"]
                )

        return _ci_report(failures)
