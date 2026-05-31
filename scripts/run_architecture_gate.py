#!/usr/bin/env python3
"""
run_architecture_gate.py — CI Engine entrypoint (pipeline consolidado WDO PROJECT 02).

Pipeline ativo (17 gates) — cobertura idêntica ao legacy de 18 gates.
FAIL em qualquer gate → exit 1.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any, Callable

WDO_CI_TIMESTAMP = "2000-01-01T00:00:00Z"
WDO_CI_RUN_LABEL = "architecture-gate-v10"
SNAPSHOT_RUNS = 20

# Referência — pipeline completo pré-consolidação (equivalência comportamental).
LEGACY_PIPELINE_STEPS: tuple[str, ...] = (
    "contract-gate",
    "evolution-gate",
    "data-gate",
    "snapshot-spec-gate",
    "audit-enforcement-gate",
    "observability-fingerprint-gate",
    "system-health-gate",
    "system-lock-gate",
    "config-freeze-gate",
    "error-taxonomy-gate",
    "watchdog-gate",
    "production-lock-gate",
    "consolidation-gate",
    "stability-gate",
    "runtime-budget-gate",
    "safe-mode-gate",
    "runtime-monitor-gate",
    "failsafe-gate",
)

# Pipeline consolidado (~11 + final-consolidation-gate).
PIPELINE_STEPS: tuple[str, ...] = (
    "contract-gate",
    "evolution-gate",
    "data-gate",
    "snapshot-spec-gate",
    "audit-observability-gate",
    "system-health-gate",
    "system-lock-gate",
    "config-freeze-gate",
    "watchdog-stability-gate",
    "production-lock-gate",
    "failsafe-gate",
    "final-consolidation-gate",
    "system-completeness-gate",
    "certification-gate",
    "long-run-validation-gate",
    "release-packaging-gate",
    "adversarial-audit-gate",
)


def _canonical_payload(reports: dict[str, dict[str, Any]]) -> str:
    return json.dumps(reports, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _run_hash(reports: dict[str, dict[str, Any]]) -> str:
    return hashlib.sha256(_canonical_payload(reports).encode("utf-8")).hexdigest()


def _print_step(step: str, report: dict[str, Any]) -> None:
    print(f"step: {step}")
    print(f"status: {report['status']}")
    for key in (
        "health_score",
        "complexity_score",
        "stability_score",
        "live_health_score",
        "behavioral_fingerprint",
        "certification_hash",
        "release_hash",
        "audit_hash",
    ):
        if key in report:
            print(f"{key}: {report[key]}")
    print("failures:")
    failures = report.get("failures", [])
    if failures:
        for failure in failures:
            print(f"  - {failure}")
    else:
        print("  - (none)")
    print()


def run_architecture_gate(*, snapshot_runs: int = SNAPSHOT_RUNS) -> dict[str, dict[str, Any]]:
    from src.ci import ContractCIGate, DataCIGate
    from src.ci.final_gates import run_system_lock_gate
    from src.ci.merged_gates import (
        run_audit_observability_gate,
        run_watchdog_stability_preamble,
        run_watchdog_stability_tail,
    )
    from src.certification import (
        run_certification_gate,
        run_long_run_validation_gate,
        run_release_packaging_gate,
    )
    from src.completeness import run_system_completeness_gate
    from src.config import run_config_freeze_gate
    from src.evolution.evolution_registry import validate_evolution_ci
    from src.failsafe import run_failsafe_gate
    from src.health.system_health_monitor import run_system_health_gate
    from src.prod_lock import run_production_lock_gate
    from src.redundancy_final import run_final_consolidation_gate
    from src.release import ReleaseController
    from src.snapshot_spec import SnapshotCIGate as SnapshotSpecCIGate

    os.environ.setdefault("WDO_CI", "1")
    ReleaseController().set_mode("ci")

    reports: dict[str, dict[str, Any]] = {}
    legacy_reports: dict[str, dict[str, Any]] = {}

    def _abort() -> bool:
        return reports and any(
            reports[k].get("status") == "FAIL"
            for k in reports
            if k in PIPELINE_STEPS
        )

    core_runners: dict[str, Callable[[], dict[str, Any]]] = {
        "contract-gate": ContractCIGate().run_full_contract_check,
        "evolution-gate": validate_evolution_ci,
        "data-gate": DataCIGate().run_full_data_check,
        "snapshot-spec-gate": lambda: SnapshotSpecCIGate(
            seed=42,
            snapshot_runs=snapshot_runs,
        ).run_full_snapshot_spec_check(),
        "system-health-gate": lambda: run_system_health_gate(
            snapshot_runs=snapshot_runs,
        ),
        "system-lock-gate": run_system_lock_gate,
    }

    for step in ("contract-gate", "evolution-gate", "data-gate", "snapshot-spec-gate"):
        report = core_runners[step]()
        reports[step] = report
        legacy_reports[step] = report
        if report.get("status") == "FAIL":
            return _finalize(reports, legacy_reports)

    merged_audit = run_audit_observability_gate()
    reports["audit-observability-gate"] = merged_audit
    legacy_reports["audit-enforcement-gate"] = merged_audit["sub_reports"][
        "audit-enforcement-gate"
    ]
    legacy_reports["observability-fingerprint-gate"] = merged_audit["sub_reports"][
        "observability-fingerprint-gate"
    ]
    if merged_audit["status"] == "FAIL":
        return _finalize(reports, legacy_reports)

    for step in ("system-health-gate", "system-lock-gate"):
        report = core_runners[step]()
        reports[step] = report
        legacy_reports[step] = report
        if report.get("status") == "FAIL":
            return _finalize(reports, legacy_reports)

    config_report = run_config_freeze_gate()
    reports["config-freeze-gate"] = config_report
    legacy_reports["config-freeze-gate"] = config_report
    if config_report["status"] == "FAIL":
        return _finalize(reports, legacy_reports)

    preamble = run_watchdog_stability_preamble(
        legacy_reports=legacy_reports,
        run_hash=_run_hash,
        legacy_steps=LEGACY_PIPELINE_STEPS,
    )
    if preamble["status"] == "FAIL":
        reports["watchdog-stability-gate"] = preamble
        return _finalize(reports, legacy_reports)

    prod_report = run_production_lock_gate()
    reports["production-lock-gate"] = prod_report
    legacy_reports["production-lock-gate"] = prod_report
    if prod_report["status"] == "FAIL":
        reports["watchdog-stability-gate"] = preamble
        return _finalize(reports, legacy_reports)

    merged_watchdog = run_watchdog_stability_tail(
        legacy_reports=legacy_reports,
        legacy_steps=LEGACY_PIPELINE_STEPS,
        preamble=preamble,
    )
    reports["watchdog-stability-gate"] = merged_watchdog
    if merged_watchdog["status"] == "FAIL":
        return _finalize(reports, legacy_reports)

    legacy_slice_17 = {
        k: legacy_reports[k] for k in LEGACY_PIPELINE_STEPS[:17]
    }
    failsafe_report = run_failsafe_gate(gate_reports=legacy_slice_17)
    reports["failsafe-gate"] = failsafe_report
    legacy_reports["failsafe-gate"] = failsafe_report
    if failsafe_report["status"] == "FAIL":
        return _finalize(reports, legacy_reports)

    final_report = run_final_consolidation_gate(
        consolidated_reports=reports,
        legacy_reports=legacy_reports,
        legacy_steps=LEGACY_PIPELINE_STEPS,
        consolidated_steps=PIPELINE_STEPS,
    )
    reports["final-consolidation-gate"] = final_report
    if final_report["status"] == "FAIL":
        return _finalize(reports, legacy_reports)

    completeness_report = run_system_completeness_gate(gate_reports=reports)
    reports["system-completeness-gate"] = completeness_report
    if completeness_report["status"] == "FAIL":
        return _finalize(reports, legacy_reports)

    cert_report = run_certification_gate(gate_reports=reports)
    reports["certification-gate"] = cert_report
    if cert_report["status"] == "FAIL":
        return _finalize(reports, legacy_reports)

    long_run_report = run_long_run_validation_gate()
    reports["long-run-validation-gate"] = long_run_report
    if long_run_report["status"] == "FAIL":
        return _finalize(reports, legacy_reports)

    packaging_report = run_release_packaging_gate(
        certificate=cert_report.get("certificate"),
    )
    reports["release-packaging-gate"] = packaging_report
    if packaging_report["status"] == "FAIL":
        return _finalize(reports, legacy_reports)

    from src.adversarial_audit import run_adversarial_audit_gate

    adversarial_report = run_adversarial_audit_gate(gate_reports=reports)
    reports["adversarial-audit-gate"] = adversarial_report

    return _finalize(reports, legacy_reports)


def _finalize(
    reports: dict[str, dict[str, Any]],
    legacy_reports: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    from src.release import ReleaseController

    reports["legacy-expanded"] = legacy_reports
    mode_report = ReleaseController().enforce_mode_constraints(gate_reports=reports)
    reports["release-mode"] = mode_report
    return reports


def main() -> int:
    print("=== WDO PROJECT 02 — ARCHITECTURE GATE (CONSOLIDATED PIPELINE v10) ===")
    print(f"run_label: {WDO_CI_RUN_LABEL}")
    print(f"timestamp: {WDO_CI_TIMESTAMP}")
    print(f"pipeline: {' → '.join(PIPELINE_STEPS)}")
    print(f"legacy_reference: {len(LEGACY_PIPELINE_STEPS)} gates")
    print()

    reports = run_architecture_gate()
    gate_only = {k: v for k, v in reports.items() if k in PIPELINE_STEPS}
    run_hash = _run_hash(gate_only)

    print(f"run_hash: {run_hash}")
    print()

    for step in PIPELINE_STEPS:
        if step not in reports:
            break
        _print_step(step, reports[step])
        if reports[step].get("status") == "FAIL":
            print("pipeline: ABORT (gate failure)")
            break

    overall = "PASS" if all(
        gate_only.get(s, {}).get("status") == "PASS" for s in PIPELINE_STEPS
    ) else "FAIL"
    print(f"overall_status: {overall}")
    print(f"run_hash: {run_hash}")

    if overall == "PASS":
        from src.certification.system_certificate import CertificateRegistry, WDO_SYSTEM_VERSION

        cert = CertificateRegistry.get(WDO_SYSTEM_VERSION)
        if cert and cert.certification_status == "CERTIFIED":
            print()
            print("WDO PROJECT 02")
            print("VERSION 1.0.0")
            print()
            print("ARCHITECTURE COMPLETE")
            print("CERTIFIED")
            print("REPRODUCIBLE")
            print("DEPLOYABLE")
            print("ADVERSARIALLY AUDITED")
            print()
            print("STATUS: CLOSED")

    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
