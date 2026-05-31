"""
live_pipeline_monitor.py — monitoramento ao vivo da execução do pipeline.
"""

from __future__ import annotations

from typing import Any


class LivePipelineMonitor:
    """Stream de progresso gate-a-gate."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def stream_pipeline_execution(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self._events.clear()
        for idx, step in enumerate(PIPELINE_STEPS):
            if step not in gate_reports:
                break
            report = gate_reports[step]
            event = {
                "sequence": idx + 1,
                "gate": step,
                "status": report.get("status", "UNKNOWN"),
                "failure_count": len(report.get("failures", [])),
            }
            self._events.append(event)
        return list(self._events)

    def track_live_gate_progress(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        stream = self.stream_pipeline_execution(gate_reports=gate_reports)
        completed = sum(1 for e in stream if e["status"] == "PASS")
        failed = sum(1 for e in stream if e["status"] == "FAIL")
        return {
            "stream": stream,
            "completed_gates": completed,
            "failed_gates": failed,
            "total_tracked": len(stream),
        }
