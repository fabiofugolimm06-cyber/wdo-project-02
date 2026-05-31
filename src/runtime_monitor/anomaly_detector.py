"""
anomaly_detector.py — detecção de spikes e latência anômala.
"""

from __future__ import annotations

from typing import Any

from src.ci_optimizer.ci_cost_analyzer import CICostAnalyzer
from src.runtime_budget.budget_config import DEFAULT_BUDGET


class AnomalyDetector:
    """Detecta anomalias de execução via perfil sintético."""

    def __init__(self) -> None:
        self._analyzer = CICostAnalyzer()

    def detect_execution_spikes(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        timings = self._analyzer.measure_gate_execution_time()["gate_timings_ms"]
        if not timings:
            return {"spikes": [], "status": "PASS", "failures": []}

        avg = sum(timings.values()) / len(timings)
        threshold = max(int(avg * 2.5), DEFAULT_BUDGET.max_gate_time // 2)
        spikes = sorted(
            [
                {"gate": gate, "synthetic_ms": ms, "threshold_ms": threshold}
                for gate, ms in timings.items()
                if ms >= threshold
                and (not gate_reports or gate in gate_reports)
            ],
            key=lambda s: s["synthetic_ms"],
            reverse=True,
        )
        failures = [
            f"spike:{s['gate']}:{s['synthetic_ms']}ms>={s['threshold_ms']}ms"
            for s in spikes
            if s["synthetic_ms"] > DEFAULT_BUDGET.max_gate_time
        ]
        return {
            "spikes": spikes,
            "status": "PASS" if not failures else "FAIL",
            "failures": sorted(failures),
            "avg_synthetic_ms": int(avg),
        }

    def detect_gate_latency_anomalies(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        spikes = self.detect_execution_spikes(gate_reports=gate_reports)
        anomalies: list[str] = []
        for spike in spikes["spikes"]:
            if spike["synthetic_ms"] > DEFAULT_BUDGET.max_gate_time:
                anomalies.append(spike["gate"])

        ordered = sorted(set(anomalies))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": [f"latency:{g}" for g in ordered],
            "anomalous_gates": ordered,
            "spike_report": spikes,
        }
