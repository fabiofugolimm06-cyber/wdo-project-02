"""
release_controller.py — enforcement de constraints por modo.
"""

from __future__ import annotations

from typing import Any

from src.release.mode_manager import ModeManager, ReleaseMode


class ReleaseController:
    """
    Controlador de modo de release.

    DEV  — permissivo, logs detalhados
    CI   — full validation, strict enforcement
    PROD — arquitetura frozen, mutation guard ON
    """

    def __init__(self, mode_manager: ModeManager | None = None) -> None:
        self._modes = mode_manager or ModeManager()

    def set_mode(self, mode: ReleaseMode | str) -> ReleaseMode:
        return self._modes.set_mode(mode)

    def get_mode(self) -> ReleaseMode:
        return self._modes.get_mode()

    def enforce_mode_constraints(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        failures: list[str] = []
        mode = self.get_mode()

        if mode == ReleaseMode.CI:
            if gate_reports:
                for gate, report in sorted(gate_reports.items()):
                    if report.get("status") == "FAIL":
                        failures.extend(
                            f"{gate}:{msg}" for msg in report.get("failures", [])
                        )
            if not failures:
                from src.system_lock import validate_system_lock

                lock = validate_system_lock()
                if lock["status"] == "FAIL":
                    failures.extend(f"system_lock:{m}" for m in lock["failures"])

        elif mode == ReleaseMode.PROD:
            from src.system_lock import MutationGuard, bootstrap_production_lock_registry

            if not self._modes.mutation_guard_enabled:
                failures.append("prod: mutation guard deve estar ON.")

            guard = MutationGuard(lock_registry=bootstrap_production_lock_registry())
            drift = guard.detect_unauthorized_mutation()
            if drift["status"] == "FAIL":
                failures.extend(f"prod:{m}" for m in drift["failures"])

            if gate_reports:
                for gate, report in sorted(gate_reports.items()):
                    if report.get("status") == "FAIL":
                        failures.append(f"prod: gate {gate} não pode falhar.")

        elif mode == ReleaseMode.DEV:
            # permissivo — não adiciona failures de gates
            pass

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "mode": mode.value,
            "strict": self._modes.is_strict,
            "mutation_guard": self._modes.mutation_guard_enabled,
            "verbose_logs": self._modes.verbose_logs,
        }
