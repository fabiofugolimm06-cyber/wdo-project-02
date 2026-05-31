"""
long_run_validator.py — validação long-run (100 ciclos determinísticos).
"""

from __future__ import annotations

import os
from typing import Any

from src.certification.reproducibility_certifier import LONG_RUN_ITERATIONS


class LongRunValidator:
    """100 execuções / replays / rollbacks / recoveries — zero divergência."""

    def __init__(self, *, iterations: int | None = None) -> None:
        self.iterations = iterations if iterations is not None else LONG_RUN_ITERATIONS

    def validate_100_run_determinism(self) -> dict[str, Any]:
        from src.certification.reproducibility_certifier import ReproducibilityCertifier

        return ReproducibilityCertifier(iterations=self.iterations).certify_determinism()

    def validate_100_snapshot_replays(self) -> dict[str, Any]:
        from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

        reference: set[str] | None = None
        failures: list[str] = []
        for i in range(self.iterations):
            registry = bootstrap_baseline_snapshot_registry()
            hashes = {spec.state_hash for spec in registry.list()}
            if reference is None:
                reference = hashes
            elif hashes != reference:
                failures.append(f"snapshot_replay: divergência no ciclo {i + 1}.")

        return {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "iterations": self.iterations,
        }

    def validate_100_rollback_cycles(self) -> dict[str, Any]:
        from src.deployment import RollbackManager, ReleaseManager

        fp = "rollback" + "0" * 58
        ReleaseManager().deploy_version(version="1.0.0", fingerprint=fp)
        failures: list[str] = []
        for i in range(self.iterations):
            report = RollbackManager().rollback_to_version(version="1.0.0")
            if report["status"] != "PASS":
                failures.append(f"rollback_cycle:{i + 1}:{report.get('failures')}")

        return {
            "status": "PASS" if not failures else "FAIL",
            "failures": sorted(set(str(f) for f in failures))[:10],
            "iterations": self.iterations,
        }

    def validate_100_recovery_cycles(self) -> dict[str, Any]:
        from src.failsafe.recovery_strategy import RecoveryStrategy

        passing = {
            g: {"status": "PASS", "failures": []}
            for g in ("contract-gate", "data-gate", "evolution-gate")
        }
        failures: list[str] = []
        for i in range(self.iterations):
            report = RecoveryStrategy().validate_post_recovery_state(
                gate_reports=passing,
            )
            if report["status"] != "PASS":
                failures.append(f"recovery_cycle:{i + 1}")

        return {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "iterations": self.iterations,
        }

    def run_full_long_run_suite(self) -> dict[str, Any]:
        checks = {
            "determinism": self.validate_100_run_determinism(),
            "snapshot_replays": self.validate_100_snapshot_replays(),
            "rollback_cycles": self.validate_100_rollback_cycles(),
            "recovery_cycles": self.validate_100_recovery_cycles(),
        }
        failures: list[str] = []
        for name, report in checks.items():
            if report["status"] != "PASS":
                failures.append(f"long_run:{name}: FAIL.")
                failures.extend(report.get("failures", [])[:3])

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "iterations": self.iterations,
            "checks": checks,
        }
