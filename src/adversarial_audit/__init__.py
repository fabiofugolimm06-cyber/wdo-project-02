"""Independent Adversarial Audit Layer."""

from src.adversarial_audit.adversarial_ci_gate import (
    REQUIRED_ATTACKS,
    AdversarialAuditGate,
    run_adversarial_audit_gate,
)
from src.adversarial_audit.audit_report import (
    AdversarialAuditReport,
    AttackResult,
    build_adversarial_audit_report,
    run_adversarial_audit,
)
from src.adversarial_audit.architecture_breaker import ArchitectureBreaker
from src.adversarial_audit.determinism_breaker import DeterminismBreaker
from src.adversarial_audit.recovery_attack_tester import RecoveryAttackTester
from src.adversarial_audit.registry_tamper_tester import RegistryTamperTester
from src.adversarial_audit.snapshot_corruption_tester import SnapshotCorruptionTester

__all__ = [
    "AdversarialAuditGate",
    "AdversarialAuditReport",
    "ArchitectureBreaker",
    "AttackResult",
    "DeterminismBreaker",
    "REQUIRED_ATTACKS",
    "RecoveryAttackTester",
    "RegistryTamperTester",
    "SnapshotCorruptionTester",
    "build_adversarial_audit_report",
    "run_adversarial_audit",
    "run_adversarial_audit_gate",
]
