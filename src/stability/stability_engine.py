"""
stability_engine.py — análise de estabilidade multi-execução e stability-gate.
"""

from __future__ import annotations

from typing import Any

from src.stability.regression_protector import RegressionProtector


class StabilityEngine:
    """Detecta instabilidade sistêmica sob múltiplas execuções determinísticas."""

    def run_full_stability_analysis(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        instability = self.detect_system_instability(gate_reports=gate_reports)
        score = self.compute_stability_score(gate_reports=gate_reports)
        failures = sorted(set(instability["failures"]))
        if score["stability_score"] < 55:
            failures.append(
                f"stability: score baixo ({score['stability_score']})."
            )
        return {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "instability": instability,
            "score": score,
        }

    def detect_system_instability(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failures: list[str] = []

        from src.observability import SystemFingerprintLogger

        fps = {SystemFingerprintLogger().compute_system_fingerprint() for _ in range(3)}
        if len(fps) != 1:
            failures.append("instability: system_fingerprint variável.")

        from src.simplification.redundancy_analyzer import RedundancyAnalyzer

        functional = RedundancyAnalyzer().detect_duplicate_validations()
        if functional:
            failures.append(
                f"instability: duplicação funcional ({len(functional)} pares)."
            )

        from src.ci_optimizer.gate_runtime_profiler import GateRuntimeProfiler

        variance = GateRuntimeProfiler().compute_variance_across_runs(runs=3)
        if not variance["stable"]:
            failures.append("instability: variance de profiling > 0.")

        for gate, report in sorted(gate_reports.items()):
            if report.get("status") != "PASS":
                failures.append(f"instability:{gate}: status != PASS.")

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
        }

    def compute_stability_score(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        from src.simplification.complexity_reducer import ComplexityReducer

        complexity = ComplexityReducer().compute_system_complexity_score()
        gate_pass_ratio = sum(
            1 for r in gate_reports.values() if r.get("status") == "PASS"
        ) / max(len(gate_reports), 1)

        from src.simplification.redundancy_analyzer import RedundancyAnalyzer

        functional_count = len(RedundancyAnalyzer().detect_duplicate_validations())

        # Score 0–100: maior = mais estável.
        base = int(complexity["complexity_score"] * 0.5 + gate_pass_ratio * 40)
        penalty = functional_count * 15
        score = max(0, min(100, base - penalty))

        return {
            "stability_score": score,
            "complexity_score": complexity["complexity_score"],
            "gate_pass_ratio": round(gate_pass_ratio, 4),
            "functional_duplicates": functional_count,
        }


def run_stability_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate CI — stability-gate (passo 14)."""
    if gate_reports is None:
        gate_reports = {}

    engine = StabilityEngine()
    analysis = engine.run_full_stability_analysis(gate_reports=gate_reports)

    protector = RegressionProtector()
    consistency = protector.validate_output_consistency(gate_reports)

    failures = sorted(set(analysis["failures"] + consistency["failures"]))
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "stability_score": analysis["score"]["stability_score"],
        "stability_analysis": analysis,
        "consistency": consistency,
    }
