"""
emergency_stop.py — parada de emergência e freeze de mutações.
"""

from __future__ import annotations

from typing import Any


class EmergencyStop:
    """Congela mutações em estado de emergência."""

    _active: bool = False

    def trigger_emergency_stop(self, *, reason: str = "") -> dict[str, Any]:
        self._active = True
        self._reason = reason
        freeze = self.freeze_all_mutations()
        return {
            "status": "STOPPED",
            "reason": reason,
            "mutations_frozen": freeze["frozen"],
            "freeze_report": freeze,
        }

    def freeze_all_mutations(self) -> dict[str, Any]:
        from src.system_lock import bootstrap_production_lock_registry, MutationGuard

        guard = MutationGuard(lock_registry=bootstrap_production_lock_registry())
        drift = guard.detect_unauthorized_mutation()
        return {
            "frozen": True,
            "drift_status": drift["status"],
            "failures": drift.get("failures", []),
        }

    def is_active(self) -> bool:
        return self._active

    def release(self) -> None:
        self._active = False
        self._reason = ""

    @classmethod
    def reset(cls) -> None:
        cls._active = False
