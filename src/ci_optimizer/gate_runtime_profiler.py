"""
gate_runtime_profiler.py — perfil determinístico de runtime por gate.
"""

from __future__ import annotations

from typing import Any

from src.ci_optimizer.ci_cost_analyzer import CICostAnalyzer


class GateRuntimeProfiler:
    """Profiling estrutural — sem reexecutar gates com parâmetros diferentes."""

    def __init__(self, pipeline_steps: tuple[str, ...] | None = None) -> None:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        self.pipeline_steps = pipeline_steps or PIPELINE_STEPS
        self._cost = CICostAnalyzer(self.pipeline_steps)

    def profile_each_gate(self) -> dict[str, Any]:
        timings = self._cost.measure_gate_execution_time()["gate_timings_ms"]
        profiles: list[dict[str, Any]] = []
        for gate in self.pipeline_steps:
            ms = timings.get(gate, 0)
            profiles.append(
                {
                    "gate": gate,
                    "synthetic_ms": ms,
                    "relative_weight": round(
                        ms / max(sum(timings.values()), 1), 4
                    ),
                }
            )
        return {"profiles": profiles, "gate_count": len(profiles)}

    def detect_bottlenecks(self, *, top_n: int = 3) -> dict[str, Any]:
        timings = self._cost.measure_gate_execution_time()["gate_timings_ms"]
        ranked = sorted(timings.items(), key=lambda kv: kv[1], reverse=True)
        bottlenecks = [
            {"gate": gate, "synthetic_ms": ms} for gate, ms in ranked[:top_n]
        ]
        return {
            "bottlenecks": bottlenecks,
            "slowest_gate": ranked[0][0] if ranked else None,
        }

    def compute_variance_across_runs(self, *, runs: int = 3) -> dict[str, Any]:
        """Variance zero esperada — perfil sintético é idempotente."""
        snapshots: list[dict[str, int]] = []
        for _ in range(runs):
            snap = self._cost.measure_gate_execution_time()["gate_timings_ms"]
            snapshots.append(dict(sorted(snap.items())))

        reference = snapshots[0]
        variance_by_gate: dict[str, int] = {}
        for gate in self.pipeline_steps:
            values = [snap.get(gate, 0) for snap in snapshots]
            variance_by_gate[gate] = max(values) - min(values)

        total_variance = sum(variance_by_gate.values())
        return {
            "runs": runs,
            "variance_by_gate": variance_by_gate,
            "total_variance": total_variance,
            "stable": total_variance == 0,
            "reference_timings_ms": reference,
        }
