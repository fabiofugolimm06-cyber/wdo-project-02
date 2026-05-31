"""
safe_mode_controller.py — controle global de modo seguro.
"""

from __future__ import annotations

from enum import Enum


class SystemMode(str, Enum):
    NORMAL = "NORMAL"
    SAFE = "SAFE"
    DEGRADED = "DEGRADED"


class SafeModeController:
    """Singleton — instabilidade → SAFE MODE automático."""

    _instance: SafeModeController | None = None
    _mode: SystemMode = SystemMode.NORMAL
    _instability_count: int = 0

    def __new__(cls) -> SafeModeController:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def enable_safe_mode(self, *, reason: str = "") -> SystemMode:
        self._mode = SystemMode.SAFE
        self._instability_count += 1
        self._last_reason = reason
        return self._mode

    def disable_safe_mode(self) -> SystemMode:
        self._mode = SystemMode.NORMAL
        return self._mode

    def enable_degraded_mode(self) -> SystemMode:
        self._mode = SystemMode.DEGRADED
        return self._mode

    def get_system_mode(self) -> SystemMode:
        return self._mode

    def auto_escalate_on_instability(self, *, failures: list[str]) -> SystemMode:
        if failures:
            return self.enable_safe_mode(reason=failures[0])
        if self._mode == SystemMode.SAFE:
            return self.disable_safe_mode()
        return self._mode

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
