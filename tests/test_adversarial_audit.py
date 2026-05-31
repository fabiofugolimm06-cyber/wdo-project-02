"""
tests/test_adversarial_audit.py — Independent Adversarial Audit Layer.
"""

from __future__ import annotations

import pytest

from src.adversarial_audit import (
    AdversarialAuditGate,
    AdversarialAuditReport,
    ArchitectureBreaker,
    AttackResult,
    DeterminismBreaker,
    REQUIRED_ATTACKS,
    RecoveryAttackTester,
    RegistryTamperTester,
    SnapshotCorruptionTester,
    build_adversarial_audit_report,
    run_adversarial_audit,
    run_adversarial_audit_gate,
)
from src.certification.system_certificate import CertificateRegistry

pytestmark = pytest.mark.slow


class TestAttackResult:
    def test_vulnerability_when_silent_breach(self):
        result = AttackResult(
            test_id="99",
            attack_name="silent_breach",
            blocked=False,
            detected=False,
        )
        assert result.vulnerability is True

    def test_no_vulnerability_when_blocked(self):
        result = AttackResult(
            test_id="01",
            attack_name="blocked_attack",
            blocked=True,
            detected=True,
        )
        assert result.vulnerability is False


class TestAdversarialAuditReport:
    def test_build_report_pass(self):
        results = [
            AttackResult("01", "a", blocked=True, detected=True),
            AttackResult("02", "b", blocked=True, detected=False),
        ]
        report = build_adversarial_audit_report(results)
        assert isinstance(report, AdversarialAuditReport)
        assert report.status == "PASS"
        assert report.tests_executed == 2
        assert report.attacks_blocked == 2
        assert report.attacks_detected == 1
        assert report.vulnerabilities_found == 0
        assert len(report.audit_hash) == 64

    def test_build_report_fail_on_vulnerability(self):
        results = [
            AttackResult("01", "a", blocked=False, detected=False),
        ]
        report = build_adversarial_audit_report(results)
        assert report.status == "FAIL"
        assert report.vulnerabilities_found == 1


class TestAdversarialAuditGate:
    def test_required_attack_coverage(self):
        assert len(REQUIRED_ATTACKS) == 10

    def test_validate_attack_coverage(self):
        report = run_adversarial_audit()
        gate = AdversarialAuditGate()
        assert gate.validate_attack_coverage(report) == []

    def test_validate_zero_undetected_vulnerabilities(self):
        report = run_adversarial_audit()
        gate = AdversarialAuditGate()
        assert gate.validate_zero_undetected_vulnerabilities(report) == []

    def test_run_gate_pass_criteria(self):
        gate_report = run_adversarial_audit_gate()
        assert gate_report["status"] == "PASS"
        assert gate_report["attacks_executed"] == 10
        assert gate_report["attacks_detected"] == 10
        assert gate_report["vulnerabilities_found"] == 0
        assert gate_report["failures"] == []
        assert len(gate_report["audit_hash"]) == 64


class TestIndividualAttacks:
    def test_contract_tampering(self):
        result = ArchitectureBreaker().test_contract_tampering()
        assert result.test_id == "01"
        assert result.blocked or result.detected

    def test_registry_overwrite_attack(self):
        result = RegistryTamperTester().test_registry_overwrite_attack()
        assert result.test_id == "02"
        assert result.blocked and result.detected

    def test_snapshot_corruption(self):
        result = SnapshotCorruptionTester().test_snapshot_corruption()
        assert result.test_id == "03"
        assert result.blocked and result.detected

    def test_evolution_chain_corruption(self):
        result = ArchitectureBreaker().test_evolution_chain_corruption()
        assert result.test_id == "04"
        assert result.blocked and result.detected

    def test_runtime_mutation_attack(self):
        result = ArchitectureBreaker().test_runtime_mutation_attack()
        assert result.test_id == "05"
        assert result.blocked and result.detected

    def test_config_mutation_attack(self):
        result = RegistryTamperTester().test_config_mutation_attack()
        assert result.test_id == "06"
        assert result.blocked and result.detected

    def test_release_artifact_modification(self):
        CertificateRegistry.reset()
        result = ArchitectureBreaker().test_release_artifact_modification()
        assert result.test_id == "07"
        assert result.blocked and result.detected

    def test_rollback_poisoning(self):
        result = RecoveryAttackTester().test_rollback_poisoning()
        assert result.test_id == "08"
        assert result.blocked and result.detected

    def test_fingerprint_collision_simulation(self):
        result = DeterminismBreaker().test_fingerprint_collision_simulation()
        assert result.test_id == "09"
        assert result.blocked and result.detected

    def test_recovery_failure_simulation(self):
        result = RecoveryAttackTester().test_recovery_failure_simulation()
        assert result.test_id == "10"
        assert result.blocked and result.detected


class TestAdversarialAuditSuite:
    def test_run_adversarial_audit_passes(self):
        report = run_adversarial_audit()
        assert report.status == "PASS"
        assert report.tests_executed == 10
        assert report.vulnerabilities_found == 0
        assert report.attacks_blocked == 10
        names = {item["attack_name"] for item in report.results}
        assert names == {attack for _, attack in REQUIRED_ATTACKS}

    def test_run_adversarial_audit_gate(self):
        gate = run_adversarial_audit_gate()
        assert gate["status"] == "PASS"
        assert gate["attacks_executed"] == 10
        assert gate["attacks_detected"] == 10
        assert gate["vulnerabilities_found"] == 0
        assert gate["failures"] == []
        assert len(gate["audit_hash"]) == 64
