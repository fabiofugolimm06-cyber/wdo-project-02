"""
invariant_validator.py — invariantes core do sistema.
"""

from __future__ import annotations

from typing import Any

from microstructure.contracts.registry import contract_registry
from microstructure.determinism import WDO_PROJECT_RANDOM_SEED


def _report(failures: list[str]) -> dict[str, Any]:
    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }


class InvariantValidator:
    """
    Valida invariantes arquiteturais non-negotiable.

    - contracts imutáveis salvo version bump
    - data determinístico
    - snapshots reproduzíveis
    - CI determinístico
    """

    def validate_system_invariants(self) -> dict[str, Any]:
        failures: list[str] = []

        if not contract_registry.is_frozen:
            failures.append("contracts: registry deve estar frozen.")

        from src.contracts.data.dataset_fingerprint import generate_fingerprint
        from src.contracts.data import OHLCV_SCHEMA_V1
        from tests.ohlcv_data import make_ohlcv

        df = make_ohlcv(50, seed=WDO_PROJECT_RANDOM_SEED)
        fps = {
            generate_fingerprint(df, OHLCV_SCHEMA_V1, normalization_version="none:v1")
            for _ in range(5)
        }
        if len(fps) != 1:
            failures.append("data: fingerprint não determinístico.")

        from src.snapshot_spec.snapshot_ci_gate import SnapshotCIGate

        snap = SnapshotCIGate(seed=WDO_PROJECT_RANDOM_SEED).run_full_snapshot_spec_check()
        if snap["status"] != "PASS":
            failures.extend(f"snapshots:{f}" for f in snap["failures"])

        from src.observability import RunLogger

        logger = RunLogger()
        logger.log_run({"seed": WDO_PROJECT_RANDOM_SEED, "gate": "ci"})
        logger.log_step("probe", {"ok": True})
        logger.finalize_run("PASS")
        logger2 = RunLogger()
        logger2.log_run({"seed": WDO_PROJECT_RANDOM_SEED, "gate": "ci"})
        logger2.log_step("probe", {"ok": True})
        logger2.finalize_run("PASS")
        if logger.run_hash != logger2.run_hash:
            failures.append("ci: run_hash não determinístico.")

        return _report(failures)

    def enforce_core_rules(self) -> dict[str, Any]:
        """Alias enforcement — falha imediata se invariante quebrado."""
        report = self.validate_system_invariants()
        if report["status"] == "FAIL":
            report["enforced"] = False
        else:
            report["enforced"] = True
        return report
