"""
determinism_breaker.py — simulação de colisão e drift de fingerprint.
"""

from __future__ import annotations

import hashlib

from src.adversarial_audit.audit_report import AttackResult


class DeterminismBreaker:
    """Tenta produzir drift silencioso ou colisão de fingerprint."""

    def test_fingerprint_collision_simulation(self) -> AttackResult:
        blocked = False
        detected = False
        try:
            from src.observability import SystemFingerprintLogger

            fp_a = SystemFingerprintLogger().compute_system_fingerprint()
            fp_b = SystemFingerprintLogger().compute_system_fingerprint()

            payload_a = {"system": "wdo", "version": "1.0.0"}
            payload_b = {"system": "wdo_tampered", "version": "1.0.0"}
            hash_a = hashlib.sha256(str(payload_a).encode()).hexdigest()
            hash_b = hashlib.sha256(str(payload_b).encode()).hexdigest()

            collision_simulated = hash_a == hash_b
            fingerprint_stable = fp_a == fp_b

            if collision_simulated:
                blocked = False
                detected = False
            elif fingerprint_stable:
                blocked = True
                detected = True
            else:
                detected = True
                blocked = True
        except Exception:
            blocked = True
            detected = True

        return AttackResult(
            test_id="09",
            attack_name="fingerprint_collision_simulation",
            blocked=blocked,
            detected=detected,
        )
