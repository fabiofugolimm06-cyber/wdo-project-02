"""Pipeline Runtime Monitor."""

from __future__ import annotations

from typing import Any

from src.runtime_monitor.anomaly_detector import AnomalyDetector
from src.runtime_monitor.live_pipeline_monitor import LivePipelineMonitor
from src.runtime_monitor.runtime_health_stream import RuntimeHealthStream


def run_runtime_monitor_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate CI — runtime-monitor-gate (passo 17)."""
    if gate_reports is None:
        gate_reports = {}

    failures: list[str] = []
    stream = RuntimeHealthStream()
    metrics = stream.emit_runtime_metrics(gate_reports=gate_reports)

    anomaly = AnomalyDetector().detect_gate_latency_anomalies(
        gate_reports=gate_reports,
    )
    failures.extend(anomaly["failures"])

    if metrics["health"]["live_health_score"] < 50:
        failures.append(
            f"monitor: live_health_score baixo "
            f"({metrics['health']['live_health_score']})."
        )

    for gate, report in sorted(gate_reports.items()):
        if report.get("status") != "PASS":
            failures.append(f"monitor:{gate}: status != PASS.")

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "live_health_score": metrics["health"]["live_health_score"],
        "runtime_metrics": metrics,
    }


__all__ = [
    "AnomalyDetector",
    "LivePipelineMonitor",
    "RuntimeHealthStream",
    "run_runtime_monitor_gate",
]
