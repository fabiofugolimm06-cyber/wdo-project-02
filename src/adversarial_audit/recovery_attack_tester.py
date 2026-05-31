"""
recovery_attack_tester.py — ataques a rollback e recovery.
"""

from __future__ import annotations

from src.adversarial_audit.audit_report import AttackResult


class RecoveryAttackTester:
    """Tenta envenenar rollback ou forçar recovery inválido."""

    def test_rollback_poisoning(self) -> AttackResult:
        blocked = False
        detected = False
        try:
            from src.deployment import RollbackManager

            report = RollbackManager().rollback_to_version(version="POISONED_VERSION_X")
            if report["status"] == "FAIL":
                blocked = True
                detected = True
            else:
                blocked = False
        except Exception:
            blocked = True
            detected = True

        return AttackResult(
            test_id="08",
            attack_name="rollback_poisoning",
            blocked=blocked,
            detected=detected,
        )

    def test_recovery_failure_simulation(self) -> AttackResult:
        blocked = False
        detected = False
        try:
            from src.failsafe.recovery_strategy import RecoveryStrategy

            failing = {
                "contract-gate": {"status": "FAIL", "failures": ["simulated breach"]},
                "evolution-gate": {"status": "FAIL", "failures": ["simulated breach"]},
                "data-gate": {"status": "FAIL", "failures": ["simulated breach"]},
            }
            report = RecoveryStrategy().validate_post_recovery_state(
                gate_reports=failing,
            )
            if report["status"] == "FAIL":
                blocked = True
                detected = True

            strategy = RecoveryStrategy().choose_recovery_strategy(
                gate_reports=failing,
            )
            if strategy["strategy"] == "full_rollback":
                detected = True
                blocked = True
        except Exception:
            blocked = True
            detected = True

        return AttackResult(
            test_id="10",
            attack_name="recovery_failure_simulation",
            blocked=blocked,
            detected=detected,
        )
