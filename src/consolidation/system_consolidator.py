"""
system_consolidator.py — consolidação end-to-end de todas as camadas.
"""

from __future__ import annotations

from typing import Any


class SystemConsolidator:
    """Agrega validação de integridade cross-layer."""

    def consolidate_all_layers(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        failures: list[str] = []
        layer_reports: dict[str, dict[str, Any]] = {}

        from src.simplification.dependency_map import DependencyMap

        dep = DependencyMap().validate_unidirectional()
        layer_reports["dependency_map"] = dep
        if dep["status"] == "FAIL":
            failures.extend(dep["failures"])

        from src.simplification.system_surface import SystemSurface

        surface = SystemSurface().expose_minimal_api_surface()
        layer_reports["system_surface"] = {"public_api_count": surface["public_api_count"]}

        from src.invariants import run_invariant_enforcement

        inv = run_invariant_enforcement(gate_reports=gate_reports)
        layer_reports["invariants"] = inv
        if inv["status"] == "FAIL":
            failures.extend(f"invariants:{f}" for f in inv["failures"])

        from src.ci_optimizer import CISimplifier

        analysis = CISimplifier().analyze_ci_pipeline()
        layer_reports["ci_analysis"] = {
            "gate_count": analysis["gate_count"],
            "complexity_score": analysis["complexity"]["complexity_score"],
        }
        if analysis["complexity"]["complexity_score"] < 25:
            failures.append(
                f"consolidation: redundância crítica (score={analysis['complexity']['complexity_score']})."
            )

        from src.ci_optimizer import PipelineOptimizer

        optimizer = PipelineOptimizer()
        optimized = optimizer.propose_optimized_pipeline()
        equiv = optimizer.validate_equivalence(optimizer.original, optimized)
        layer_reports["pipeline_optimizer"] = equiv
        if equiv["status"] == "FAIL":
            failures.extend(f"optimizer:{f}" for f in equiv["failures"])

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "layers": layer_reports,
        }

    def validate_end_to_end_integrity(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failures: list[str] = []

        for gate, report in sorted(gate_reports.items()):
            if report.get("status") != "PASS":
                failures.append(f"e2e:{gate} status={report.get('status')}.")

        from src.health.consistency_checker import ConsistencyChecker

        cross = ConsistencyChecker().cross_layer_validation()
        if cross["status"] == "FAIL":
            failures.extend(f"cross_layer:{f}" for f in cross["failures"])

        consolidation = self.consolidate_all_layers(gate_reports=gate_reports)
        if consolidation["status"] == "FAIL":
            failures.extend(consolidation["failures"])

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
        }
