"""
version_bundle.py — bundle versionado com hash reproduzível.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.certification.system_certificate import (
    CertificateRegistry,
    WDO_RELEASE_NAME,
    WDO_SYSTEM_VERSION,
)
from src.release_packaging.artifact_builder import ArtifactBuilder
from src.release_packaging.release_manifest import ReleaseManifest


def _hash_payload(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class VersionBundle:
    """Gera artefato oficial WDO_PROJECT_02_v1.0.0."""

    def build_official_release(
        self,
        *,
        certificate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        failures: list[str] = []

        cert_record = CertificateRegistry.get(WDO_SYSTEM_VERSION)
        cert = certificate or (cert_record.to_dict() if cert_record else {})

        if not cert or cert.get("certification_status") != "PASS":
            failures.append("bundle: certificado v1.0.0 PASS obrigatório.")

        manifest = ReleaseManifest().build(certificate=cert)
        artifact = ArtifactBuilder().build_artifact(manifest=manifest, certificate=cert)
        release_hash = _hash_payload(artifact)

        repeat = _hash_payload(artifact)
        if release_hash != repeat:
            failures.append("bundle: release_hash instável.")

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "release_name": WDO_RELEASE_NAME,
            "release_hash": release_hash,
            "bundle": artifact,
            "reproducible": release_hash == repeat,
        }
