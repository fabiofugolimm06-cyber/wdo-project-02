"""
certification_gates.py — gates CI de certificação, long-run e packaging.
"""

from __future__ import annotations

from typing import Any

from src.certification.architecture_certifier import ArchitectureCertifier
from src.certification.deployment_certifier import DeploymentCertifier
from src.certification.long_run_validator import LongRunValidator
from src.certification.reproducibility_certifier import ReproducibilityCertifier
from src.certification.system_certificate import (
    CertificateRegistry,
    build_system_certificate,
)


def run_certification_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate CI — certification-gate."""
    failures: list[str] = []

    arch = ArchitectureCertifier().certify_all()
    repro = ReproducibilityCertifier().certify_determinism()
    repro_snap = ReproducibilityCertifier().certify_snapshot_reproducibility()
    repro_cross = ReproducibilityCertifier().certify_cross_run_equivalence()

    deploy_ready = DeploymentCertifier().certify_production_readiness()
    deploy_api = DeploymentCertifier().certify_external_api()

    repro_combined = {
        "status": "PASS"
        if all(
            r["status"] == "PASS"
            for r in (repro, repro_snap, repro_cross)
        )
        else "FAIL",
        "failures": sorted(
            set(
                repro.get("failures", [])
                + repro_snap.get("failures", [])
                + repro_cross.get("failures", [])
            )
        ),
    }

    deploy_combined = {
        "status": "PASS"
        if deploy_ready["status"] == "PASS" and deploy_api["status"] == "PASS"
        else "FAIL",
        "failures": sorted(
            set(deploy_ready.get("failures", []) + deploy_api.get("failures", []))
        ),
    }

    certificate = build_system_certificate(
        architecture_report=arch,
        reproducibility_report=repro_combined,
        deployment_report=deploy_combined,
    )

    if arch["status"] != "PASS":
        failures.extend(arch.get("failures", []))
    if repro_combined["status"] != "PASS":
        failures.extend(repro_combined.get("failures", []))
    if deploy_combined["status"] != "PASS":
        failures.extend(deploy_combined.get("failures", []))
    if certificate.certification_status != "PASS":
        failures.append("certification: status != PASS.")

    reg = CertificateRegistry.register(certificate)
    if reg["status"] != "PASS":
        failures.extend(reg.get("failures", []))

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "certificate": certificate.to_dict(),
        "architecture": arch,
        "reproducibility": repro_combined,
        "deployment": deploy_combined,
    }


def run_long_run_validation_gate() -> dict[str, Any]:
    """Gate CI — long-run-validation-gate."""
    report = LongRunValidator().run_full_long_run_suite()
    return {
        "status": report["status"],
        "failures": report["failures"],
        "iterations": report["iterations"],
        "checks": report["checks"],
    }


def run_release_packaging_gate(
    *,
    certificate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gate CI — release-packaging-gate."""
    from src.release_packaging.version_bundle import VersionBundle

    failures: list[str] = []
    if certificate and certificate.get("certification_status") != "PASS":
        failures.append("packaging: certificado não PASS.")

    bundle_report = VersionBundle().build_official_release(certificate=certificate)
    if bundle_report["status"] != "PASS":
        failures.extend(bundle_report.get("failures", []))

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "bundle": bundle_report.get("bundle"),
        "release_hash": bundle_report.get("release_hash"),
        "release_name": bundle_report.get("release_name"),
    }
