"""
recovery_strategy.py — estratégias de recuperação pós-falha.
"""

from __future__ import annotations

from typing import Any

from src.failsafe.rollback_controller import RollbackController
from src.safe_mode.degraded_mode import DegradedMode
from src.safe_mode.safe_mode_controller import SafeModeController, SystemMode


class RecoveryStrategy:
    """Escolhe e valida estratégia de recuperação."""

    def choose_recovery_strategy(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failed_gates = [
            g for g, r in sorted(gate_reports.items()) if r.get("status") != "PASS"
        ]

        if not failed_gates:
            return {
                "strategy": "none",
                "action": "continue_normal",
                "system_mode": SystemMode.NORMAL.value,
            }

        if len(failed_gates) <= 2:
            return {
                "strategy": "degraded_retry",
                "action": "enable_degraded_mode",
                "disabled_gates": DegradedMode().disable_non_critical_gates(),
                "failed_gates": failed_gates,
            }

        return {
            "strategy": "full_rollback",
            "action": "rollback_to_baseline",
            "failed_gates": failed_gates,
        }

    def validate_post_recovery_state(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failures: list[str] = []
        strategy = self.choose_recovery_strategy(gate_reports=gate_reports)

        if strategy["strategy"] == "none":
            rollback = RollbackController().restore_snapshot()
            if rollback["status"] == "FAIL":
                failures.extend(rollback["failures"])
            controller = SafeModeController()
            if controller.get_system_mode() not in {SystemMode.NORMAL, SystemMode.SAFE}:
                controller.disable_safe_mode()

        elif strategy["strategy"] == "full_rollback":
            rollback = RollbackController().rollback_to_last_stable_state(
                gate_reports=gate_reports,
            )
            failures.extend(rollback["failures"])

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "strategy": strategy,
        }
