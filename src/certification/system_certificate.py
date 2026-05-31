"""
system_certificate.py — certificado determinístico WDO v1.0.0.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

WDO_SYSTEM_VERSION = "1.0.0"
WDO_CERTIFICATION_TIMESTAMP = "2000-01-01T00:00:00Z"
WDO_RELEASE_NAME = "WDO_PROJECT_02_v1.0.0"


@dataclass(frozen=True)
class SystemCertificate:
    """Certificado imutável — v1.0.0 não altera após emissão."""

    system_version: str
    architecture_hash: str
    certification_hash: str
    certification_timestamp_fixed: str
    certification_status: str
    adversarial_audit_hash: str = ""
    adversarial_audit_status: str = "PENDING"

    def to_dict(self) -> dict[str, str]:
        return {
            "system_version": self.system_version,
            "architecture_hash": self.architecture_hash,
            "certification_hash": self.certification_hash,
            "certification_timestamp_fixed": self.certification_timestamp_fixed,
            "certification_status": self.certification_status,
            "adversarial_audit_hash": self.adversarial_audit_hash,
            "adversarial_audit_status": self.adversarial_audit_status,
            "release_name": WDO_RELEASE_NAME,
        }


class CertificateRegistry:
    """Registry append-only — v1.0.0 imutável após registro."""

    _certificates: dict[str, SystemCertificate] = {}

    @classmethod
    def register(cls, certificate: SystemCertificate) -> dict[str, Any]:
        version = certificate.system_version
        if version in cls._certificates:
            existing = cls._certificates[version]
            if existing.certification_hash != certificate.certification_hash:
                return {
                    "status": "FAIL",
                    "failures": [
                        f"certificate: v{version} imutável — hash diverge."
                    ],
                }
            return {"status": "PASS", "failures": [], "certificate": existing.to_dict()}
        cls._certificates[version] = certificate
        return {"status": "PASS", "failures": [], "certificate": certificate.to_dict()}

    @classmethod
    def finalize_adversarial_audit(
        cls,
        *,
        adversarial_audit_hash: str,
        adversarial_audit_status: str,
        architecture_pass: bool,
        long_run_pass: bool,
        release_pass: bool,
        adversarial_pass: bool,
    ) -> dict[str, Any]:
        """Promove certificado para CERTIFIED após adversarial-audit-gate PASS."""
        version = WDO_SYSTEM_VERSION
        existing = cls._certificates.get(version)
        if existing is None:
            return {
                "status": "FAIL",
                "failures": ["certificate: ausente para finalize adversarial."],
            }

        all_pass = all(
            (
                architecture_pass,
                long_run_pass,
                release_pass,
                adversarial_pass,
            )
        )
        finalized = SystemCertificate(
            system_version=existing.system_version,
            architecture_hash=existing.architecture_hash,
            certification_hash=existing.certification_hash,
            certification_timestamp_fixed=existing.certification_timestamp_fixed,
            certification_status="CERTIFIED" if all_pass else "FAIL",
            adversarial_audit_hash=adversarial_audit_hash,
            adversarial_audit_status=adversarial_audit_status,
        )
        cls._certificates[version] = finalized

        failures: list[str] = []
        if not all_pass:
            failures.append("certificate: status != CERTIFIED.")
        if adversarial_audit_status != "PASS":
            failures.append("certificate: adversarial_audit_status != PASS.")

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "certificate": finalized.to_dict(),
        }

    @classmethod
    def get(cls, version: str) -> SystemCertificate | None:
        return cls._certificates.get(version)

    @classmethod
    def reset(cls) -> None:
        cls._certificates = {}


def compute_architecture_hash() -> str:
    from src.observability import SystemFingerprintLogger

    return SystemFingerprintLogger().compute_system_fingerprint()


def build_system_certificate(
    *,
    architecture_report: dict[str, Any],
    reproducibility_report: dict[str, Any],
    deployment_report: dict[str, Any],
) -> SystemCertificate:
    architecture_hash = compute_architecture_hash()
    payload = {
        "system_version": WDO_SYSTEM_VERSION,
        "architecture_hash": architecture_hash,
        "architecture_status": architecture_report.get("status"),
        "reproducibility_status": reproducibility_report.get("status"),
        "deployment_status": deployment_report.get("status"),
        "timestamp": WDO_CERTIFICATION_TIMESTAMP,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    certification_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

    all_pass = all(
        r.get("status") == "PASS"
        for r in (architecture_report, reproducibility_report, deployment_report)
    )
    return SystemCertificate(
        system_version=WDO_SYSTEM_VERSION,
        architecture_hash=architecture_hash,
        certification_hash=certification_hash,
        certification_timestamp_fixed=WDO_CERTIFICATION_TIMESTAMP,
        certification_status="PASS" if all_pass else "FAIL",
        adversarial_audit_hash="",
        adversarial_audit_status="PENDING",
    )
