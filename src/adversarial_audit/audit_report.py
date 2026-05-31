"""
audit_report.py — relatório adversarial e orquestração da auditoria.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class AttackResult:
    """Resultado de um ataque simulado."""

    test_id: str
    attack_name: str
    blocked: bool
    detected: bool

    @property
    def vulnerability(self) -> bool:
        """Ataque passou silenciosamente — nunca permitido."""
        return not self.blocked and not self.detected


@dataclass
class AdversarialAuditReport:
    """Relatório final da auditoria adversarial independente."""

    tests_executed: int
    attacks_blocked: int
    attacks_detected: int
    vulnerabilities_found: int
    audit_hash: str
    status: str
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tests_executed": self.tests_executed,
            "attacks_blocked": self.attacks_blocked,
            "attacks_detected": self.attacks_detected,
            "vulnerabilities_found": self.vulnerabilities_found,
            "audit_hash": self.audit_hash,
            "status": self.status,
            "results": self.results,
        }


def _hash_results(results: list[AttackResult]) -> str:
    payload = [
        {
            "test_id": r.test_id,
            "attack_name": r.attack_name,
            "blocked": r.blocked,
            "detected": r.detected,
            "vulnerability": r.vulnerability,
        }
        for r in results
    ]
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_adversarial_audit_report(results: list[AttackResult]) -> AdversarialAuditReport:
    vulnerabilities = sum(1 for r in results if r.vulnerability)
    blocked = sum(1 for r in results if r.blocked)
    detected = sum(1 for r in results if r.detected)
    status = "PASS" if vulnerabilities == 0 else "FAIL"
    return AdversarialAuditReport(
        tests_executed=len(results),
        attacks_blocked=blocked,
        attacks_detected=detected,
        vulnerabilities_found=vulnerabilities,
        audit_hash=_hash_results(results),
        status=status,
        results=[
            {
                "test_id": r.test_id,
                "attack_name": r.attack_name,
                "blocked": r.blocked,
                "detected": r.detected,
                "vulnerability": r.vulnerability,
            }
            for r in results
        ],
    )


def run_adversarial_audit() -> AdversarialAuditReport:
    """Executa suite completa de 10 ataques simulados."""
    from src.adversarial_audit.architecture_breaker import ArchitectureBreaker
    from src.adversarial_audit.determinism_breaker import DeterminismBreaker
    from src.adversarial_audit.recovery_attack_tester import RecoveryAttackTester
    from src.adversarial_audit.registry_tamper_tester import RegistryTamperTester
    from src.adversarial_audit.snapshot_corruption_tester import SnapshotCorruptionTester

    runners: list[Callable[[], AttackResult]] = [
        ArchitectureBreaker().test_contract_tampering,
        RegistryTamperTester().test_registry_overwrite_attack,
        SnapshotCorruptionTester().test_snapshot_corruption,
        ArchitectureBreaker().test_evolution_chain_corruption,
        ArchitectureBreaker().test_runtime_mutation_attack,
        RegistryTamperTester().test_config_mutation_attack,
        ArchitectureBreaker().test_release_artifact_modification,
        RecoveryAttackTester().test_rollback_poisoning,
        DeterminismBreaker().test_fingerprint_collision_simulation,
        RecoveryAttackTester().test_recovery_failure_simulation,
    ]
    results = [runner() for runner in runners]
    return build_adversarial_audit_report(results)


def run_adversarial_audit_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Atalho — delega para ``AdversarialAuditGate``."""
    from src.adversarial_audit.adversarial_ci_gate import (
        run_adversarial_audit_gate as _run_gate,
    )

    return _run_gate(gate_reports=gate_reports)
