"""
metrics_exporter.py — exportação de métricas CI/runtime para consumo externo.
"""

from __future__ import annotations

from typing import Any


class MetricsExporter:
    """Exporta métricas determinísticas do sistema."""

    def export_ci_metrics(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from src.ci_optimizer import CICostAnalyzer, GateRuntimeProfiler

        cost = CICostAnalyzer().compute_total_pipeline_cost()
        profile = GateRuntimeProfiler().profile_each_gate()

        passed = 0
        failed = 0
        if gate_reports:
            for report in gate_reports.values():
                if isinstance(report, dict):
                    if report.get("status") == "PASS":
                        passed += 1
                    elif report.get("status") == "FAIL":
                        failed += 1

        return {
            "total_cost_units": cost["total_cost_units"],
            "total_synthetic_ms": cost["total_ms"],
            "gate_count": cost["gate_count"],
            "gate_profiles": profile["profiles"],
            "gates_passed": passed,
            "gates_failed": failed,
        }

    def export_stability_score(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from src.stability import StabilityEngine

        reports = gate_reports or {}
        score = StabilityEngine().compute_stability_score(gate_reports=reports)
        return {
            "stability_score": score["stability_score"],
            "gate_pass_ratio": score["gate_pass_ratio"],
            "complexity_score": score["complexity_score"],
        }
