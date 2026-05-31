"""
pipeline_monitor.py — monitor de runs de pipeline CI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineMonitor:
    """Rastreia sucesso/falha por gate de forma determinística."""

    _runs: list[dict[str, Any]] = field(default_factory=list)

    def record_run(
        self,
        *,
        run_id: str,
        run_hash: str,
        gate_reports: dict[str, dict[str, Any]],
    ) -> None:
        self._runs.append(
            {
                "run_id": run_id,
                "run_hash": run_hash,
                "gate_reports": {
                    gate: {
                        "status": report.get("status"),
                        "failure_count": len(report.get("failures", [])),
                    }
                    for gate, report in sorted(gate_reports.items())
                },
            }
        )

    def track_run_success_rate(self) -> dict[str, Any]:
        if not self._runs:
            return {"total_runs": 0, "success_rate": 1.0, "gate_success_rate": {}}

        total = len(self._runs)
        successes = sum(
            1
            for run in self._runs
            if all(
                g["status"] == "PASS"
                for g in run["gate_reports"].values()
            )
        )
        gate_stats: dict[str, dict[str, Any]] = {}
        for run in self._runs:
            for gate, info in run["gate_reports"].items():
                stats = gate_stats.setdefault(gate, {"pass": 0, "total": 0})
                stats["total"] += 1
                if info["status"] == "PASS":
                    stats["pass"] += 1

        gate_success_rate = {
            gate: stats["pass"] / stats["total"]
            for gate, stats in sorted(gate_stats.items())
        }
        return {
            "total_runs": total,
            "success_rate": successes / total,
            "gate_success_rate": gate_success_rate,
        }

    def detect_flaky_gate(self, *, threshold: float = 1.0) -> dict[str, Any]:
        stats = self.track_run_success_rate()
        failures: list[str] = []
        for gate, rate in stats.get("gate_success_rate", {}).items():
            if rate < threshold:
                failures.append(
                    f"flaky_gate:{gate}: success_rate={rate:.4f} < {threshold}."
                )
        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "flaky": bool(ordered),
        }

    def isolate_failure_source(
        self,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        sources: list[str] = []
        for gate, report in sorted(gate_reports.items()):
            if report.get("status") == "FAIL":
                sources.append(gate)
        return {
            "failure_sources": sources,
            "primary_source": sources[0] if sources else None,
        }

    @property
    def runs(self) -> list[dict[str, Any]]:
        return list(self._runs)
