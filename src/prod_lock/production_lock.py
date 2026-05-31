"""
production_lock.py — hard lock de produção (read-only system graph).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.prod_lock.runtime_guard import RuntimeGuard
from src.release.mode_manager import ModeManager, ReleaseMode


@dataclass
class ProductionLock:
    """
    PROD = arquitetura frozen + mutation guard + config lock.

    Qualquer mutation runtime → FAIL.
    """

    _enabled: bool = field(default=False, init=False)
    _runtime_guard: RuntimeGuard = field(default_factory=RuntimeGuard)

    def enable_production_mode(self) -> None:
        ModeManager().set_mode(ReleaseMode.PROD)
        self._enabled = True
        self._runtime_guard.freeze_execution_graph()

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enforce_read_only_runtime(self) -> dict[str, Any]:
        failures: list[str] = []
        mode = ModeManager().get_mode()
        if mode != ReleaseMode.PROD and not self._enabled:
            # CI valida capacidade prod lock sem ativar PROD global
            mode = ReleaseMode.CI

        if mode == ReleaseMode.PROD and not self._enabled:
            failures.append("prod: production mode não habilitado.")

        guard_report = self._runtime_guard.enforce_static_execution_graph()
        if guard_report["status"] == "FAIL":
            failures.extend(guard_report["failures"])

        from src.system_lock import validate_system_lock

        lock = validate_system_lock()
        if lock["status"] == "FAIL":
            failures.extend(f"system_lock:{m}" for m in lock["failures"])

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "production_mode": self._enabled,
        }

    def block_dynamic_schema_changes(self) -> dict[str, Any]:
        failures: list[str] = []
        from src.config import run_config_freeze_gate

        config = run_config_freeze_gate()
        if config["status"] == "FAIL":
            failures.extend(f"config:{m}" for m in config["failures"])

        from microstructure.contracts.registry import contract_registry

        if not contract_registry.is_frozen:
            failures.append("prod: contract registry deve estar frozen.")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
        }


def run_production_lock_gate() -> dict[str, Any]:
    """Gate CI — production-lock-gate."""
    from src.release.mode_manager import ModeManager

    modes = ModeManager()
    prior = modes.get_mode()
    lock = ProductionLock()
    lock.enable_production_mode()
    read_only = lock.enforce_read_only_runtime()
    schema = lock.block_dynamic_schema_changes()
    modes.set_mode(prior)
    failures = sorted(set(read_only["failures"] + schema["failures"]))
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
