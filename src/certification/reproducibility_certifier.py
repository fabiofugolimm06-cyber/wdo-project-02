"""
reproducibility_certifier.py — certificação de determinismo e equivalência.
"""

from __future__ import annotations

import os
from typing import Any

LONG_RUN_ITERATIONS = int(os.environ.get("WDO_LONG_RUN_ITERATIONS", "100"))


class ReproducibilityCertifier:
    """100 execuções idênticas — zero drift."""

    def __init__(self, *, iterations: int | None = None) -> None:
        self.iterations = iterations if iterations is not None else LONG_RUN_ITERATIONS

    def certify_determinism(self) -> dict[str, Any]:
        from src.observability import SystemFingerprintLogger

        fingerprints: set[str] = set()
        for _ in range(self.iterations):
            fingerprints.add(SystemFingerprintLogger().compute_system_fingerprint())

        failures: list[str] = []
        if len(fingerprints) != 1:
            failures.append(
                f"determinism: {len(fingerprints)} fingerprints em {self.iterations} runs."
            )
        fp = next(iter(fingerprints)) if fingerprints else ""
        return {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "iterations": self.iterations,
            "fingerprint": fp,
            "invariant": len(fingerprints) == 1,
        }

    def certify_snapshot_reproducibility(self) -> dict[str, Any]:
        from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

        reference: frozenset[str] | None = None
        failures: list[str] = []
        for i in range(self.iterations):
            registry = bootstrap_baseline_snapshot_registry()
            hashes = frozenset(spec.state_hash for spec in registry.list())
            if not hashes:
                failures.append("snapshot: nenhum state_hash.")
                break
            if reference is None:
                reference = hashes
            elif hashes != reference:
                failures.append(f"snapshot: divergência no replay {i + 1}.")

        return {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "iterations": self.iterations,
            "unique_state_hashes": sorted(reference or ()),
            "invariant": not failures,
        }

    def certify_cross_run_equivalence(self) -> dict[str, Any]:
        from src.api.pipeline_endpoint import PipelineEndpoint

        old_ci = os.environ.pop("WDO_CI", None)
        fingerprints: set[str] = set()
        failures: list[str] = []
        try:
            endpoint = PipelineEndpoint()
            for _ in range(min(self.iterations, 10)):
                result = endpoint.execute_full_pipeline(snapshot_runs=3)
                if result["status"] != "PASS":
                    failures.extend(result.get("failures", []))
                    break
                fingerprints.add(result["fingerprint"])
        finally:
            if old_ci is not None:
                os.environ["WDO_CI"] = old_ci

        if len(fingerprints) != 1 and not failures:
            failures.append(
                f"equivalence: {len(fingerprints)} fingerprints em cross-run."
            )
        return {
            "status": "PASS" if not failures else "FAIL",
            "failures": sorted(set(failures)),
            "fingerprint": next(iter(fingerprints)) if fingerprints else "",
            "invariant": len(fingerprints) == 1,
        }
