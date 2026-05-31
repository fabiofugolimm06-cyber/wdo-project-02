"""
merged_gates.py — gates consolidados (mesma cobertura, menos steps).
"""

from __future__ import annotations

from typing import Any, Callable

from src.ci.final_gates import (
    run_audit_enforcement_gate,
    run_error_taxonomy_gate,
    run_observability_fingerprint_gate,
)
from src.consolidation import run_consolidation_gate
from src.runtime_budget import run_runtime_budget_gate
from src.runtime_monitor import run_runtime_monitor_gate
from src.safe_mode import run_safe_mode_gate
from src.stability import run_stability_gate
from src.watchdog import run_watchdog_gate


def _merge_sub_reports(
    gate_name: str,
    sub_reports: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    failures: list[str] = []
    for sub_gate, report in sorted(sub_reports.items()):
        failures.extend(report.get("failures", []))
        if report.get("status") != "PASS":
            failures.append(f"{gate_name}: sub-gate {sub_gate} FAIL.")

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "sub_reports": sub_reports,
        "merged_from": sorted(sub_reports.keys()),
    }


def run_audit_observability_gate() -> dict[str, Any]:
    """audit+observability-gate — merge audit-enforcement + observability-fingerprint."""
    sub = {
        "audit-enforcement-gate": run_audit_enforcement_gate(),
        "observability-fingerprint-gate": run_observability_fingerprint_gate(),
    }
    return _merge_sub_reports("audit-observability-gate", sub)


def run_watchdog_stability_preamble(
    *,
    legacy_reports: dict[str, dict[str, Any]],
    run_hash: Callable[[dict[str, dict[str, Any]]], str],
    legacy_steps: tuple[str, ...],
) -> dict[str, Any]:
    """Fase 1 — error-taxonomy + watchdog (legacy gates 10–11)."""
    failures: list[str] = []
    slice_9 = {k: legacy_reports[k] for k in legacy_steps[:9]}

    error_report = run_error_taxonomy_gate(
        slice_9,
        run_id=run_hash(slice_9)[:16],
    )
    legacy_reports["error-taxonomy-gate"] = error_report
    if error_report["status"] == "FAIL":
        failures.extend(error_report.get("failures", []))
    else:
        watchdog_report = run_watchdog_gate(
            gate_reports=slice_9,
            run_hash=run_hash(slice_9),
        )
        legacy_reports["watchdog-gate"] = watchdog_report
        if watchdog_report["status"] == "FAIL":
            failures.extend(watchdog_report.get("failures", []))

    sub = {
        k: legacy_reports[k]
        for k in ("error-taxonomy-gate", "watchdog-gate")
        if k in legacy_reports
    }
    merged = _merge_sub_reports("watchdog-stability-gate", sub)
    merged["failures"] = sorted(set(failures + merged["failures"]))
    merged["status"] = "PASS" if not merged["failures"] else "FAIL"
    merged["phase"] = "preamble"
    return merged


def run_watchdog_stability_tail(
    *,
    legacy_reports: dict[str, dict[str, Any]],
    legacy_steps: tuple[str, ...],
    preamble: dict[str, Any],
) -> dict[str, Any]:
    """Fase 2 — consolidation → monitor (legacy gates 13–17, após production-lock)."""
    failures: list[str] = list(preamble.get("failures", []))

    slice_12 = {k: legacy_reports[k] for k in legacy_steps[:12]}
    consolidation_report = run_consolidation_gate(gate_reports=slice_12)
    legacy_reports["consolidation-gate"] = consolidation_report
    if consolidation_report["status"] == "FAIL":
        failures.extend(consolidation_report.get("failures", []))
    else:
        slice_13 = {k: legacy_reports[k] for k in legacy_steps[:13]}
        stability_report = run_stability_gate(gate_reports=slice_13)
        legacy_reports["stability-gate"] = stability_report
        if stability_report["status"] == "FAIL":
            failures.extend(stability_report.get("failures", []))
        else:
            slice_14 = {k: legacy_reports[k] for k in legacy_steps[:14]}
            budget_report = run_runtime_budget_gate(gate_reports=slice_14)
            legacy_reports["runtime-budget-gate"] = budget_report
            if budget_report["status"] == "FAIL":
                failures.extend(budget_report.get("failures", []))
            else:
                slice_15 = {k: legacy_reports[k] for k in legacy_steps[:15]}
                safe_report = run_safe_mode_gate(gate_reports=slice_15)
                legacy_reports["safe-mode-gate"] = safe_report
                if safe_report["status"] == "FAIL":
                    failures.extend(safe_report.get("failures", []))
                else:
                    slice_16 = {k: legacy_reports[k] for k in legacy_steps[:16]}
                    monitor_report = run_runtime_monitor_gate(gate_reports=slice_16)
                    legacy_reports["runtime-monitor-gate"] = monitor_report
                    if monitor_report["status"] == "FAIL":
                        failures.extend(monitor_report.get("failures", []))

    sub_reports = dict(preamble.get("sub_reports", {}))
    for key in (
        "consolidation-gate",
        "stability-gate",
        "runtime-budget-gate",
        "safe-mode-gate",
        "runtime-monitor-gate",
    ):
        if key in legacy_reports:
            sub_reports[key] = legacy_reports[key]

    merged = _merge_sub_reports("watchdog-stability-gate", sub_reports)
    merged["failures"] = sorted(set(failures + merged["failures"]))
    merged["status"] = "PASS" if not merged["failures"] else "FAIL"
    merged["phase"] = "complete"
    if "stability-gate" in legacy_reports:
        merged["stability_score"] = legacy_reports["stability-gate"].get(
            "stability_score"
        )
    if "runtime-monitor-gate" in legacy_reports:
        merged["live_health_score"] = legacy_reports["runtime-monitor-gate"].get(
            "live_health_score"
        )
    return merged
