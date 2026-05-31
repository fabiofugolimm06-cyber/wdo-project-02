"""
rollback_manager.py — rollback de versão e restore de snapshot.
"""

from __future__ import annotations

from typing import Any

from src.deployment.version_manager import VersionManager


class RollbackManager:
    """Recuperação pós-falha externa."""

    def rollback_to_version(self, *, version: str) -> dict[str, Any]:
        manager = VersionManager()
        record = manager.get_version(version)
        if record is None:
            return {
                "status": "FAIL",
                "failures": [f"rollback: versão {version!r} não encontrada."],
            }

        snapshot = self.restore_snapshot_state()
        if snapshot["status"] == "FAIL":
            return {
                "status": "FAIL",
                "failures": snapshot["failures"],
                "version": version,
            }

        return {
            "status": "PASS",
            "failures": [],
            "version": version,
            "fingerprint": record.fingerprint,
            "snapshot": snapshot,
        }

    def restore_snapshot_state(self) -> dict[str, Any]:
        from src.failsafe.rollback_controller import RollbackController

        return RollbackController().restore_snapshot()
