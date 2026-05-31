"""
invariant_validator.py — validação e enforcement de invariantes.
"""

from __future__ import annotations

from typing import Any

from src.invariants.invariant_registry import InvariantRegistry, bootstrap_system_invariants


class InvariantValidator:
    """Valida invariantes do sistema — violação = FAIL."""

    def __init__(self, registry: InvariantRegistry | None = None) -> None:
        self.registry = registry or bootstrap_system_invariants()
        self._baseline_snapshot_hash: str | None = None

    def validate_system_invariants(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        failures: list[str] = []

        chain = self.registry.validate_invariant_chain()
        if not chain["valid"]:
            failures.extend(chain["errors"])

        from microstructure.contracts.registry import contract_registry

        if not contract_registry.is_frozen:
            failures.append("invariant:contracts_immutable — registry não frozen.")

        from src.simplification.dependency_map import DependencyMap

        dep = DependencyMap().validate_unidirectional()
        if dep["status"] == "FAIL":
            failures.extend(f"invariant:no_circular_deps:{e}" for e in dep["failures"])

        from src.observability import SystemFingerprintLogger

        fp1 = SystemFingerprintLogger().compute_system_fingerprint()
        fp2 = SystemFingerprintLogger().compute_system_fingerprint()
        if fp1 != fp2:
            failures.append("invariant:ci_deterministic — system fingerprint instável.")

        if gate_reports:
            for gate, report in gate_reports.items():
                if report.get("status") == "FAIL":
                    failures.append(f"invariant:gate_pass:{gate} falhou.")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
        }

    def enforce_non_regression(
        self,
        *,
        system_state_hash: str,
        validation_results: dict[str, Any],
    ) -> dict[str, Any]:
        snapshot = self.registry.build_snapshot(
            snapshot_id="invariant_baseline_v1",
            system_state_hash=system_state_hash,
            validation_results=validation_results,
        )
        current_hash = snapshot.invariant_set_hash

        failures: list[str] = []
        if self._baseline_snapshot_hash is None:
            self._baseline_snapshot_hash = current_hash
        elif self._baseline_snapshot_hash != current_hash:
            failures.append(
                "invariant:non_regression — invariant_set mutou após registro."
            )

        if snapshot.system_state_hash != system_state_hash:
            failures.append("invariant:system_state_hash inconsistente.")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "snapshot": snapshot.to_dict(),
        }


def run_invariant_enforcement(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
    system_state_hash: str | None = None,
) -> dict[str, Any]:
    from src.observability import SystemFingerprintLogger

    validator = InvariantValidator()
    validation = validator.validate_system_invariants(gate_reports=gate_reports)
    state_hash = system_state_hash or SystemFingerprintLogger().compute_system_fingerprint()
    regression = validator.enforce_non_regression(
        system_state_hash=state_hash,
        validation_results=validation,
    )

    failures = sorted(set(validation["failures"] + regression["failures"]))
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "system_state_hash": state_hash,
    }
