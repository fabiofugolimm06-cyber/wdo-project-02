"""
mode_manager.py — gestão de modo de execução (dev | ci | prod).
"""

from __future__ import annotations

import os
from enum import Enum


class ReleaseMode(str, Enum):
    DEV = "dev"
    CI = "ci"
    PROD = "prod"


class ModeManager:
    """
    Singleton de modo — ``WDO_RELEASE_MODE`` ou ``WDO_CI=1`` → ci.
    """

    _instance: ModeManager | None = None
    _mode: ReleaseMode = ReleaseMode.DEV

    def __new__(cls) -> ModeManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._bootstrap_from_env()
        return cls._instance

    def _bootstrap_from_env(self) -> None:
        if os.environ.get("WDO_CI") == "1":
            self._mode = ReleaseMode.CI
            return
        env_mode = os.environ.get("WDO_RELEASE_MODE", "").strip().lower()
        if env_mode in {m.value for m in ReleaseMode}:
            self._mode = ReleaseMode(env_mode)

    def get_mode(self) -> ReleaseMode:
        return self._mode

    def set_mode(self, mode: ReleaseMode | str) -> ReleaseMode:
        if isinstance(mode, str):
            mode = ReleaseMode(mode.strip().lower())
        self._mode = mode
        return self._mode

    @property
    def is_strict(self) -> bool:
        return self._mode in {ReleaseMode.CI, ReleaseMode.PROD}

    @property
    def mutation_guard_enabled(self) -> bool:
        return self._mode in {ReleaseMode.CI, ReleaseMode.PROD}

    @property
    def verbose_logs(self) -> bool:
        return self._mode == ReleaseMode.DEV

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (somente testes)."""
        cls._instance = None
