"""Safe Mode Switch global."""

from __future__ import annotations

from typing import Any

from src.safe_mode.degraded_mode import DegradedMode
from src.safe_mode.emergency_stop import EmergencyStop
from src.safe_mode.safe_mode_controller import SafeModeController, SystemMode


def run_safe_mode_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate CI — safe-mode-gate (passo 16)."""
    if gate_reports is None:
        gate_reports = {}

    failures: list[str] = []
    controller = SafeModeController()
    stop = EmergencyStop()

    prior_failures: list[str] = []
    for gate, report in sorted(gate_reports.items()):
        if report.get("status") != "PASS":
            prior_failures.append(f"{gate}: status != PASS")

    mode = controller.auto_escalate_on_instability(failures=prior_failures)

    if prior_failures:
        failures.extend(prior_failures)
    elif mode != SystemMode.NORMAL:
        failures.append(f"safe_mode: modo inesperado {mode.value} com pipeline PASS.")

    if stop.is_active():
        failures.append("safe_mode: emergency_stop ativo.")

    freeze = stop.freeze_all_mutations()
    if freeze["drift_status"] == "FAIL":
        failures.extend(
            f"safe_mode:freeze:{msg}" for msg in freeze.get("failures", [])
        )

    ordered = sorted(set(failures))
    status = "PASS" if not ordered else "FAIL"
    if status == "PASS":
        controller.disable_safe_mode()

    return {
        "status": status,
        "failures": ordered,
        "system_mode": controller.get_system_mode().value,
        "degraded_scope": DegradedMode().reduce_ci_scope(),
        "mutations_frozen_check": freeze["frozen"],
    }


__all__ = [
    "DegradedMode",
    "EmergencyStop",
    "SafeModeController",
    "SystemMode",
    "run_safe_mode_gate",
]
