"""
system_completeness_gate.py — gate final de completude operacional.
"""

from __future__ import annotations

import os
from typing import Any


def validate_full_system_operational_readiness(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    failures: list[str] = []

    from src.api import WDOApi

    snapshot = WDOApi().get_latest_snapshot()
    if snapshot["status"] != "PASS":
        failures.extend(snapshot.get("failures", []))

    from src.deployment import RollbackManager

    rollback = RollbackManager().restore_snapshot_state()
    if rollback["status"] != "PASS":
        failures.extend(rollback.get("failures", []))

    from src.observability_export import MetricsExporter, TraceExporter

    metrics = MetricsExporter().export_ci_metrics(gate_reports=gate_reports)
    if metrics["gate_count"] < 1:
        failures.append("readiness: gate_count inválido.")

    trace = TraceExporter().export_dependency_graph()
    if trace["total_edges"] < 1:
        failures.append("readiness: dependency graph vazio.")

    if gate_reports:
        for step in (
            "final-consolidation-gate",
            "failsafe-gate",
            "production-lock-gate",
        ):
            if gate_reports.get(step, {}).get("status") != "PASS":
                failures.append(f"readiness:{step}: não PASS.")

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "metrics": metrics,
        "trace_edges": trace["total_edges"],
    }


def check_external_execution_capability() -> dict[str, Any]:
    failures: list[str] = []

    from src.api import WDOApi

    api = WDOApi()
    gate_report = api.execute_gate("contract-gate")
    if gate_report.get("status") != "PASS":
        failures.extend(gate_report.get("failures", []))

    health = api.get_system_health(snapshot_runs=3)
    if health.get("status") != "PASS":
        failures.extend(health.get("failures", []))

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "external_api": True,
    }


def verify_no_ci_dependency_for_core_execution() -> dict[str, Any]:
    failures: list[str] = []
    old_ci = os.environ.pop("WDO_CI", None)

    try:
        from src.runtime import ProductionEngine

        result = ProductionEngine().execute_pipeline(snapshot_runs=3)
        if result["status"] != "PASS":
            failures.extend(result.get("failures", []))
        if not result.get("fingerprint"):
            failures.append("ci_free: fingerprint ausente.")
    finally:
        if old_ci is not None:
            os.environ["WDO_CI"] = old_ci

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "ci_independent": not ordered,
    }


def assert_deterministic_reproducibility_outside_ci() -> dict[str, Any]:
    failures: list[str] = []
    old_ci = os.environ.pop("WDO_CI", None)

    try:
        from src.api.pipeline_endpoint import PipelineEndpoint

        endpoint = PipelineEndpoint()
        fp_a = endpoint.execute_full_pipeline(snapshot_runs=3)["fingerprint"]
        fp_b = endpoint.execute_full_pipeline(snapshot_runs=3)["fingerprint"]
        if fp_a != fp_b:
            failures.append(
                f"repro: fingerprint diverge ({fp_a[:12]}… != {fp_b[:12]}…)."
            )
    finally:
        if old_ci is not None:
            os.environ["WDO_CI"] = old_ci

    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "deterministic": not ordered,
    }


def run_system_completeness_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate CI — system-completeness-gate (passo 13)."""
    if gate_reports is None:
        gate_reports = {}

    failures: list[str] = []

    readiness = validate_full_system_operational_readiness(gate_reports=gate_reports)
    failures.extend(readiness["failures"])

    external = check_external_execution_capability()
    failures.extend(external["failures"])

    ci_free = verify_no_ci_dependency_for_core_execution()
    failures.extend(ci_free["failures"])

    repro = assert_deterministic_reproducibility_outside_ci()
    failures.extend(repro["failures"])

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "readiness": readiness,
        "external_execution": external,
        "ci_independent": ci_free,
        "reproducibility": repro,
    }
