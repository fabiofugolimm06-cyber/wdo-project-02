"""
system_overlap_analyzer.py — matriz de overlap e validações duplicadas.
"""

from __future__ import annotations

from typing import Any

from src.simplification.gate_overlap_detector import GateOverlapDetector


# Cobertura legacy preservada por gates consolidados.
CONSOLIDATED_COVERAGE: dict[str, tuple[str, ...]] = {
    "audit-observability-gate": (
        "audit-enforcement-gate",
        "observability-fingerprint-gate",
    ),
    "watchdog-stability-gate": (
        "error-taxonomy-gate",
        "watchdog-gate",
        "consolidation-gate",
        "stability-gate",
        "runtime-budget-gate",
        "safe-mode-gate",
        "runtime-monitor-gate",
    ),
}


class SystemOverlapAnalyzer:
    """Analisa overlap no pipeline consolidado vs cobertura legacy."""

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS
        self._detector = GateOverlapDetector(self.pipeline_steps)

    def compute_system_overlap_matrix(self) -> dict[str, Any]:
        matrix: dict[str, dict[str, int]] = {}
        gates = list(self.pipeline_steps)
        for gate_a in gates:
            matrix[gate_a] = {}
            for gate_b in gates:
                matrix[gate_a][gate_b] = self._detector.compute_overlap_score(
                    gate_a, gate_b
                )
        return {
            "matrix": matrix,
            "gate_count": len(gates),
            "legacy_coverage": {
                k: list(v) for k, v in sorted(CONSOLIDATED_COVERAGE.items())
            },
        }

    def detect_duplicate_validations(self) -> list[dict[str, Any]]:
        duplicates: list[dict[str, Any]] = []
        for item in self._detector.identify_redundant_checks():
            if item["kind"] == "functional":
                duplicates.append(
                    {
                        "gates": (item["gate_a"], item["gate_b"]),
                        "overlap_score": item["overlap_score"],
                        "severity": "critical",
                    }
                )
        return duplicates
