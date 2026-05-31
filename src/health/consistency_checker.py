"""
consistency_checker.py — validação cruzada entre camadas.
"""

from __future__ import annotations

from typing import Any

from microstructure.contracts.registry import CONTRACT_TYPES, contract_registry
from src.observability.system_fingerprint_logger import SystemFingerprintLogger


def _report(failures: list[str]) -> dict[str, Any]:
    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "drift_detected": bool(ordered),
    }


class ConsistencyChecker:
    """Detecta drift e inconsistências entre contracts, data, evolution e snapshots."""

    def __init__(self) -> None:
        self._fp = SystemFingerprintLogger()

    def cross_layer_validation(self) -> dict[str, Any]:
        failures: list[str] = []

        for contract_type in CONTRACT_TYPES:
            active = contract_registry.get_active_contract(contract_type)
            contract_id = active.contract_id

            from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

            for spec in bootstrap_baseline_snapshot_registry().list():
                if spec.pipeline_stage == "ml" and contract_type == "ml_pipeline":
                    if spec.contract_id != contract_id:
                        failures.append(
                            f"snapshot↔contract: ML spec {spec.snapshot_id} "
                            f"contract_id={spec.contract_id!r} != {contract_id!r}."
                        )
                if spec.pipeline_stage == "full" and contract_type == "full_pipeline":
                    if spec.contract_id != contract_id:
                        failures.append(
                            f"snapshot↔contract: E2E spec {spec.snapshot_id} "
                            f"contract_id={spec.contract_id!r} != {contract_id!r}."
                        )

        from src.evolution.evolution_registry import bootstrap_pipeline_evolution_registry

        evo = bootstrap_pipeline_evolution_registry()
        for contract_type in CONTRACT_TYPES:
            versions = evo.list_versions(contract_type)
            if not versions:
                failures.append(f"evolution↔contract: sem versão para {contract_type!r}.")
            active_version = contract_registry.get_active_version(contract_type)
            if not any(v.version == active_version for v in versions):
                failures.append(
                    f"evolution↔contract: versão ativa {active_version!r} "
                    f"ausente em evolution para {contract_type!r}."
                )

        from src.ci.data_ci_gate import build_canonical_dataset_registry

        data_reg, _ = build_canonical_dataset_registry()
        if not data_reg.list():
            failures.append("data↔pipeline: registry de datasets vazio.")

        return _report(failures)

    def detect_cross_layer_drift(self) -> dict[str, Any]:
        """Compara fingerprints de camadas — drift sem autorização = FAIL."""
        failures: list[str] = []
        components = self._fp.log_global_state()["components"]

        fp_a = dict(components)
        fp_b = self._fp.log_global_state()["components"]

        for key in sorted(fp_a):
            if fp_a[key] != fp_b[key]:
                failures.append(f"cross_layer_drift:{key}: fingerprint instável.")

        checker = ConsistencyChecker()
        cross = checker.cross_layer_validation()
        if cross["status"] == "FAIL":
            failures.extend(cross["failures"])

        return _report(failures)
