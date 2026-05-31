"""
final_consolidation_gate.py — gate final de equivalência pós-redução.
"""

from __future__ import annotations

from typing import Any

from src.redundancy_final.system_overlap_analyzer import SystemOverlapAnalyzer
from src.redundancy_final.validation_equivalence_engine import (
    ValidationEquivalenceEngine,
    compute_behavioral_fingerprint,
)


def run_full_system_equivalence_check(
    *,
    legacy_reports: dict[str, dict[str, Any]],
    consolidated_reports: dict[str, dict[str, Any]],
    legacy_steps: tuple[str, ...],
) -> dict[str, Any]:
    engine = ValidationEquivalenceEngine()
    failures: list[str] = []

    missing = [g for g in legacy_steps if g not in legacy_reports]
    if missing:
        failures.append(f"equivalence: legacy gates ausentes: {missing}.")

    identity = engine.enforce_behavioral_identity(legacy_reports)
    failures.extend(identity["failures"])

    coverage = engine.project_consolidated_to_legacy(
        consolidated_reports,
        legacy_reports,
    )
    failures.extend(coverage["failures"])

    functional = SystemOverlapAnalyzer().detect_duplicate_validations()
    if functional:
        failures.append(
            f"equivalence: duplicação funcional ({len(functional)} pares)."
        )

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "behavioral_fingerprint": identity["behavioral_fingerprint"],
        "coverage": coverage,
    }


def validate_pipeline_reduction_integrity(
    *,
    legacy_steps: tuple[str, ...],
    consolidated_steps: tuple[str, ...],
) -> dict[str, Any]:
    failures: list[str] = []
    if len(consolidated_steps) >= len(legacy_steps):
        failures.append(
            "reduction: pipeline consolidado deve ter menos gates que legacy."
        )

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "legacy_gate_count": len(legacy_steps),
        "consolidated_gate_count": len(consolidated_steps),
        "reduction_ratio": round(
            1 - len(consolidated_steps) / max(len(legacy_steps), 1),
            4,
        ),
    }


def assert_deterministic_output(
    reports: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    fp_once = compute_behavioral_fingerprint(reports)
    fp_twice = compute_behavioral_fingerprint(reports)
    failures: list[str] = []
    if fp_once != fp_twice:
        failures.append("determinism: fingerprint instável.")
    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "fingerprint": fp_once,
    }


def assert_zero_behavioral_drift(
    *,
    legacy_reports: dict[str, dict[str, Any]],
    reference_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    engine = ValidationEquivalenceEngine()
    reference = reference_reports or legacy_reports
    equiv = engine.verify_system_equivalence(reference, legacy_reports)
    return equiv


def run_final_consolidation_gate(
    *,
    consolidated_reports: dict[str, dict[str, Any]],
    legacy_reports: dict[str, dict[str, Any]],
    legacy_steps: tuple[str, ...] | None = None,
    consolidated_steps: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Gate CI — final-consolidation-gate."""
    from scripts.run_architecture_gate import LEGACY_PIPELINE_STEPS, PIPELINE_STEPS

    legacy = legacy_steps or LEGACY_PIPELINE_STEPS
    consolidated = consolidated_steps or PIPELINE_STEPS

    failures: list[str] = []
    equiv = run_full_system_equivalence_check(
        legacy_reports=legacy_reports,
        consolidated_reports=consolidated_reports,
        legacy_steps=legacy,
    )
    failures.extend(equiv["failures"])

    reduction = validate_pipeline_reduction_integrity(
        legacy_steps=legacy,
        consolidated_steps=consolidated,
    )
    failures.extend(reduction["failures"])

    determinism = assert_deterministic_output(legacy_reports)
    failures.extend(determinism["failures"])

    drift = assert_zero_behavioral_drift(legacy_reports=legacy_reports)
    failures.extend(drift["failures"])

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "equivalence": equiv,
        "reduction": reduction,
        "determinism": determinism,
        "drift": drift,
        "behavioral_fingerprint": equiv.get("behavioral_fingerprint"),
    }
