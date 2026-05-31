"""
runtime_health_stream.py — score de saúde ao vivo e métricas de runtime.
"""

from __future__ import annotations

from typing import Any

from src.runtime_monitor.anomaly_detector import AnomalyDetector
from src.runtime_monitor.live_pipeline_monitor import LivePipelineMonitor


class RuntimeHealthStream:
    """Emite métricas de runtime durante execução CI."""

    def compute_live_health_score(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        progress = LivePipelineMonitor().track_live_gate_progress(
            gate_reports=gate_reports,
        )
        total = max(progress["total_tracked"], 1)
        pass_ratio = progress["completed_gates"] / total
        anomaly = AnomalyDetector().detect_gate_latency_anomalies(
            gate_reports=gate_reports,
        )
        penalty = len(anomaly["anomalous_gates"]) * 10
        score = max(0, min(100, int(pass_ratio * 100) - penalty))

        return {
            "live_health_score": score,
            "pass_ratio": round(pass_ratio, 4),
            "completed_gates": progress["completed_gates"],
            "failed_gates": progress["failed_gates"],
        }

    def emit_runtime_metrics(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        from src.runtime_budget.runtime_enforcer import RuntimeEnforcer

        health = self.compute_live_health_score(gate_reports=gate_reports)
        budget = RuntimeEnforcer().track_runtime_metrics(gate_reports=gate_reports)
        progress = LivePipelineMonitor().track_live_gate_progress(
            gate_reports=gate_reports,
        )
        return {
            "health": health,
            "budget_metrics": budget,
            "progress": progress,
        }
