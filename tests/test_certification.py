"""
tests/test_certification.py — certification, long-run gates, release packaging.
"""

from __future__ import annotations

import os

import pytest

from scripts.run_architecture_gate import PIPELINE_STEPS, run_architecture_gate
from src.adversarial_audit import run_adversarial_audit_gate
from src.certification import (
    ArchitectureCertifier,
    CertificateRegistry,
    ReproducibilityCertifier,
    SystemCertificate,
    WDO_SYSTEM_VERSION,
    run_certification_gate,
    run_long_run_validation_gate,
    run_release_packaging_gate,
)
from src.deployment import VersionManager
from src.release import ModeManager
from src.release_packaging import VersionBundle
from src.safe_mode import EmergencyStop, SafeModeController

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def _reset():
    ModeManager.reset()
    VersionManager.reset()
    CertificateRegistry.reset()
    SafeModeController.reset()
    EmergencyStop.reset()
    yield
    ModeManager.reset()
    VersionManager.reset()
    CertificateRegistry.reset()
    SafeModeController.reset()
    EmergencyStop.reset()


class TestCertifiers:
    def test_architecture_certifier(self):
        report = ArchitectureCertifier().certify_all()
        assert report["status"] == "PASS", report["failures"]

    def test_reproducibility_certifier(self):
        report = ReproducibilityCertifier(iterations=10).certify_determinism()
        assert report["status"] == "PASS", report["failures"]

    def test_system_certificate_immutable(self):
        cert = SystemCertificate(
            system_version=WDO_SYSTEM_VERSION,
            architecture_hash="a" * 64,
            certification_hash="b" * 64,
            certification_timestamp_fixed="2000-01-01T00:00:00Z",
            certification_status="PASS",
        )
        reg1 = CertificateRegistry.register(cert)
        reg2 = CertificateRegistry.register(cert)
        assert reg1["status"] == "PASS"
        assert reg2["status"] == "PASS"

    def test_finalize_adversarial_audit_certified(self):
        cert = SystemCertificate(
            system_version=WDO_SYSTEM_VERSION,
            architecture_hash="a" * 64,
            certification_hash="b" * 64,
            certification_timestamp_fixed="2000-01-01T00:00:00Z",
            certification_status="PASS",
        )
        CertificateRegistry.register(cert)
        finalized = CertificateRegistry.finalize_adversarial_audit(
            adversarial_audit_hash="c" * 64,
            adversarial_audit_status="PASS",
            architecture_pass=True,
            long_run_pass=True,
            release_pass=True,
            adversarial_pass=True,
        )
        assert finalized["status"] == "PASS", finalized["failures"]
        stored = CertificateRegistry.get(WDO_SYSTEM_VERSION)
        assert stored is not None
        assert stored.certification_status == "CERTIFIED"
        assert stored.adversarial_audit_hash == "c" * 64
        assert stored.adversarial_audit_status == "PASS"


class TestReleasePackaging:
    def test_bundle_requires_certificate(self):
        report = VersionBundle().build_official_release()
        assert report["status"] == "FAIL"

    def test_bundle_with_certificate(self):
        cert_report = run_certification_gate()
        assert cert_report["status"] == "PASS", cert_report["failures"]
        bundle = VersionBundle().build_official_release(
            certificate=cert_report["certificate"],
        )
        assert bundle["status"] == "PASS", bundle["failures"]
        assert bundle["release_hash"]
        assert bundle["release_name"] == "WDO_PROJECT_02_v1.0.0"


class TestCertificationGates:
    def test_long_run_gate(self):
        report = run_long_run_validation_gate()
        assert report["status"] == "PASS", report["failures"]

    def test_release_packaging_gate(self):
        cert = run_certification_gate()
        pkg = run_release_packaging_gate(certificate=cert["certificate"])
        assert pkg["status"] == "PASS", pkg["failures"]

    def test_adversarial_gate_finalizes_certificate(self):
        cert = run_certification_gate()
        long_run = run_long_run_validation_gate()
        pkg = run_release_packaging_gate(certificate=cert["certificate"])
        gate_reports = {
            "certification-gate": cert,
            "long-run-validation-gate": long_run,
            "release-packaging-gate": pkg,
        }
        adversarial = run_adversarial_audit_gate(gate_reports=gate_reports)
        assert adversarial["status"] == "PASS", adversarial["failures"]
        stored = CertificateRegistry.get(WDO_SYSTEM_VERSION)
        assert stored is not None
        assert stored.certification_status == "CERTIFIED"
        assert stored.adversarial_audit_status == "PASS"
        assert len(stored.adversarial_audit_hash) == 64


class TestPipelineV10:
    def test_seventeen_gates(self):
        assert len(PIPELINE_STEPS) == 17
        assert PIPELINE_STEPS[-4:] == (
            "certification-gate",
            "long-run-validation-gate",
            "release-packaging-gate",
            "adversarial-audit-gate",
        )

    def test_full_pipeline_passes(self):
        os.environ["WDO_CI"] = "1"
        reports = run_architecture_gate(snapshot_runs=5)
        for step in PIPELINE_STEPS:
            assert step in reports, f"missing {step}"
            assert reports[step]["status"] == "PASS", reports[step].get("failures")

        from src.certification.system_certificate import CertificateRegistry

        cert = CertificateRegistry.get(WDO_SYSTEM_VERSION)
        assert cert is not None
        assert cert.certification_status == "CERTIFIED"
        assert cert.adversarial_audit_status == "PASS"
