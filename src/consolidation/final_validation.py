"""
final_validation.py — validação final de determinismo e zero drift.
"""

from __future__ import annotations

from typing import Any

from src.consolidation.system_consolidator import SystemConsolidator


class FinalValidation:
    """Validação final do sistema consolidado."""

    def run_full_system_validation(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        consolidator = SystemConsolidator()
        e2e = consolidator.validate_end_to_end_integrity(gate_reports=gate_reports)
        drift = self.validate_zero_drift_state()
        repro = self.confirm_deterministic_reproducibility()

        failures = sorted(
            set(e2e["failures"] + drift["failures"] + repro["failures"])
        )
        return {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "e2e": e2e,
            "drift": drift,
            "reproducibility": repro,
        }

    def validate_zero_drift_state(self) -> dict[str, Any]:
        failures: list[str] = []

        from src.system_lock import bootstrap_production_lock_registry, MutationGuard

        guard = MutationGuard(lock_registry=bootstrap_production_lock_registry())
        drift = guard.detect_unauthorized_mutation()
        if drift["status"] == "FAIL":
            failures.extend(drift["failures"])

        from src.simplification.dependency_map import DependencyMap

        if DependencyMap().detect_circular_dependencies()["circular"]:
            failures.append("drift: dependências circulares detectadas.")

        ordered = sorted(failures)
        return {"status": "PASS" if not ordered else "FAIL", "failures": ordered}

    def confirm_deterministic_reproducibility(self) -> dict[str, Any]:
        failures: list[str] = []

        from src.observability import SystemFingerprintLogger

        fps = {SystemFingerprintLogger().compute_system_fingerprint() for _ in range(3)}
        if len(fps) != 1:
            failures.append("reproducibility: system_fingerprint instável (3 runs).")

        from src.observability import RunLogger

        logs: list[str] = []
        for _ in range(2):
            logger = RunLogger()
            logger.log_run({"gate": "consolidation", "seed": 42})
            logger.log_step("validate", {"ok": True})
            logger.finalize_run("PASS")
            logs.append(logger.run_hash)
        if len(set(logs)) != 1:
            failures.append("reproducibility: run_hash instável.")

        ordered = sorted(failures)
        return {"status": "PASS" if not ordered else "FAIL", "failures": ordered}


def run_consolidation_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate CI — consolidation-gate."""
    if gate_reports is None:
        gate_reports = {}

    # Se pipeline anterior passou, gate_reports contém gates 1-12 PASS.
    validation = FinalValidation().run_full_system_validation(gate_reports=gate_reports)

    from src.simplification.complexity_reducer import ComplexityReducer

    complexity = ComplexityReducer().compute_system_complexity_score()

    failures = list(validation["failures"])
    if complexity["complexity_score"] < 20:
        failures.append(
            f"consolidation: redundância crítica (score={complexity['complexity_score']})."
        )

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "complexity_score": complexity["complexity_score"],
        "system_validation": validation,
    }
