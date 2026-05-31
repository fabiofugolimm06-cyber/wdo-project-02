"""
release_manifest.py — manifesto oficial da release WDO v1.0.0.
"""

from __future__ import annotations

from typing import Any

from src.certification.system_certificate import (
    WDO_RELEASE_NAME,
    WDO_SYSTEM_VERSION,
    WDO_CERTIFICATION_TIMESTAMP,
)


class ReleaseManifest:
    """Manifesto determinístico da release."""

    def build(self, *, certificate: dict[str, Any] | None = None) -> dict[str, Any]:
        from src.observability import SystemFingerprintLogger

        logger = SystemFingerprintLogger()
        cert = certificate or {}

        return {
            "release_name": WDO_RELEASE_NAME,
            "system_version": WDO_SYSTEM_VERSION,
            "timestamp": WDO_CERTIFICATION_TIMESTAMP,
            "contracts_fingerprint": logger.compute_contracts_fingerprint(),
            "data_fingerprint": logger.compute_data_fingerprint(),
            "system_fingerprint": logger.compute_system_fingerprint(),
            "certificate_hash": cert.get("certification_hash", ""),
            "architecture_hash": cert.get("architecture_hash", ""),
        }
