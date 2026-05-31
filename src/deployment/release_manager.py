"""
release_manager.py — deploy e promoção para produção.
"""

from __future__ import annotations

from typing import Any

from src.deployment.version_manager import VersionManager


class ReleaseManager:
    """Gerencia deploy de versões."""

    def deploy_version(
        self,
        *,
        version: str,
        fingerprint: str,
    ) -> dict[str, Any]:
        manager = VersionManager()
        record = manager.register_version(version=version, fingerprint=fingerprint)
        return {
            "status": "PASS",
            "failures": [],
            "version": record.version,
            "fingerprint": record.fingerprint,
            "deployed": True,
        }

    def promote_to_production(self, *, version: str) -> dict[str, Any]:
        manager = VersionManager()
        record = manager.get_version(version)
        if record is None:
            return {
                "status": "FAIL",
                "failures": [f"promote: versão {version!r} não encontrada."],
            }

        tag_result = manager.tag_release(version=version, tag="production")
        if tag_result["status"] == "FAIL":
            return tag_result

        from src.release import ReleaseController

        ReleaseController().set_mode("prod")
        return {
            "status": "PASS",
            "failures": [],
            "version": version,
            "tag": "production",
            "fingerprint": record.fingerprint,
        }
