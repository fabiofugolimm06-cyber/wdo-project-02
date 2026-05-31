"""
degraded_mode.py — redução de escopo CI em modo degradado.
"""

from __future__ import annotations

from typing import Any


class DegradedMode:
    """Desabilita gates não-críticos em modo degradado."""

    _NON_CRITICAL_GATES: frozenset[str] = frozenset(
        {
            "audit-enforcement-gate",
            "error-taxonomy-gate",
            "observability-fingerprint-gate",
            "audit-observability-gate",
        }
    )

    def disable_non_critical_gates(
        self,
        pipeline_steps: tuple[str, ...] | None = None,
    ) -> list[str]:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        steps = pipeline_steps or PIPELINE_STEPS
        return sorted(g for g in steps if g in self._NON_CRITICAL_GATES)

    def reduce_ci_scope(self) -> dict[str, Any]:
        return {
            "snapshot_runs": 5,
            "disabled_gates": self.disable_non_critical_gates(),
            "scope": "minimal_critical_path",
        }

    def apply_degraded_pipeline(
        self,
        pipeline_steps: tuple[str, ...] | None = None,
    ) -> tuple[str, ...]:
        from scripts.run_architecture_gate import PIPELINE_STEPS

        steps = pipeline_steps or PIPELINE_STEPS
        disabled = set(self.disable_non_critical_gates(steps))
        return tuple(g for g in steps if g not in disabled)
