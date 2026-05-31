"""
health_endpoint.py — health score e failure report.
"""

from __future__ import annotations

from typing import Any


class HealthEndpoint:
    """Endpoint de saúde do sistema."""

    def return_system_health_score(
        self,
        *,
        snapshot_runs: int = 5,
    ) -> dict[str, Any]:
        from src.health.system_health_monitor import run_system_health_gate

        report = run_system_health_gate(snapshot_runs=snapshot_runs)
        return {
            "status": report.get("status", "FAIL"),
            "health_score": report.get("health_score", 0),
            "failures": report.get("failures", []),
        }

    def return_failure_report(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        failures: list[str] = []
        if gate_reports:
            for gate, report in sorted(gate_reports.items()):
                if report.get("status") != "PASS":
                    for msg in report.get("failures", []):
                        failures.append(f"{gate}:{msg}")
        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "failure_count": len(ordered),
        }
