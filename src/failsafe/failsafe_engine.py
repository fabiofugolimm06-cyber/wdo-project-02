"""
failsafe_engine.py — engine de failsafe e failsafe-gate.
"""

from __future__ import annotations

from typing import Any

from src.failsafe.recovery_strategy import RecoveryStrategy
from src.failsafe.rollback_controller import RollbackController
from src.safe_mode.emergency_stop import EmergencyStop
from src.safe_mode.safe_mode_controller import SafeModeController, SystemMode


class FailsafeEngine:
    """Detecta falhas estruturais e isola camada faulty."""

    def detect_system_failure(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failures: list[str] = []
        faulty_layers: list[str] = []

        from src.simplification.complexity_reducer import _GATE_LAYERS

        for gate, report in sorted(gate_reports.items()):
            if report.get("status") != "PASS":
                failures.append(f"failsafe:{gate}: FAIL.")
                layer = _GATE_LAYERS.get(gate, "unknown")
                faulty_layers.append(layer)

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "faulty_layers": sorted(set(faulty_layers)),
            "failure_detected": bool(ordered),
        }

    def trigger_safe_rollback(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        detection = self.detect_system_failure(gate_reports=gate_reports)
        if detection["status"] == "PASS":
            rollback = RollbackController().restore_snapshot()
            return {
                "status": "PASS",
                "failures": [],
                "rollback": rollback,
                "rollback_required": False,
            }

        rollback = RollbackController().rollback_to_last_stable_state(
            gate_reports=gate_reports,
        )
        SafeModeController().enable_safe_mode(reason="structural_failure")
        return {
            "status": rollback["status"],
            "failures": sorted(set(detection["failures"] + rollback["failures"])),
            "rollback": rollback,
            "rollback_required": True,
        }

    def isolate_faulty_layer(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        detection = self.detect_system_failure(gate_reports=gate_reports)
        return {
            "isolated_layers": detection["faulty_layers"],
            "isolation_active": bool(detection["faulty_layers"]),
            "detection": detection,
        }


def run_failsafe_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate CI — failsafe-gate (passo 18)."""
    if gate_reports is None:
        gate_reports = {}

    failures: list[str] = []
    engine = FailsafeEngine()

    detection = engine.detect_system_failure(gate_reports=gate_reports)
    failures.extend(detection["failures"])

    rollback = RollbackController().restore_snapshot()
    if rollback["status"] == "FAIL":
        failures.extend(rollback["failures"])

    recovery = RecoveryStrategy().validate_post_recovery_state(
        gate_reports=gate_reports,
    )
    failures.extend(recovery["failures"])

    # Fallback sempre disponível — snapshot baseline acessível.
    if rollback["status"] != "PASS":
        failures.append("failsafe: fallback snapshot indisponível.")
    else:
        fallback_ready = {
            "snapshot_id": rollback["snapshot_id"],
            "state_hash": rollback["state_hash"],
        }

    stop = EmergencyStop()
    if stop.is_active() and detection["status"] == "PASS":
        stop.release()

    controller = SafeModeController()
    if detection["status"] == "PASS" and controller.get_system_mode() == SystemMode.SAFE:
        controller.disable_safe_mode()

    ordered = sorted(set(failures))
    report: dict[str, Any] = {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "detection": detection,
        "rollback": rollback,
        "recovery": recovery,
        "fallback_available": rollback["status"] == "PASS",
    }
    if rollback["status"] == "PASS":
        report["fallback"] = fallback_ready
    return report
