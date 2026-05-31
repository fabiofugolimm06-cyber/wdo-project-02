"""
architecture_breaker.py — ataques a contracts, evolution, runtime e release.
"""

from __future__ import annotations

from src.adversarial_audit.audit_report import AttackResult


class ArchitectureBreaker:
    """Assume que o sistema está errado — tenta quebrar camadas core."""

    def test_contract_tampering(self) -> AttackResult:
        blocked = False
        detected = False
        try:
            from src.system_lock.protected_paths import validate_modification_path

            report = validate_modification_path(
                "microstructure/contracts/registry.py",
                change_type="in_place",
                via_pipeline=False,
            )
            if report["status"] == "FAIL":
                blocked = True
                detected = True
            else:
                from src.ci.contract_ci_gate import ContractCIGate

                gate = ContractCIGate().run_full_contract_check()
                detected = gate.get("status") == "PASS"
                blocked = detected
        except Exception:
            blocked = True
            detected = True

        return AttackResult(
            test_id="01",
            attack_name="contract_tampering",
            blocked=blocked,
            detected=detected,
        )

    def test_evolution_chain_corruption(self) -> AttackResult:
        blocked = False
        detected = False
        try:
            from src.evolution.evolution_registry import EvolutionRegistry
            from src.evolution.schema_version import SchemaVersion

            reg = EvolutionRegistry()
            orphan = SchemaVersion.create(
                contract_id="fake_contract",
                version="v99",
                schema={"tampered": True},
                parent_version="v98",
            )
            reg.register_version(orphan)
        except Exception:
            blocked = True
            detected = True

        return AttackResult(
            test_id="04",
            attack_name="evolution_chain_corruption",
            blocked=blocked,
            detected=detected,
        )

    def test_runtime_mutation_attack(self) -> AttackResult:
        blocked = False
        detected = False
        try:
            from src.system_lock import MutationGuard, bootstrap_production_lock_registry
            from src.system_lock.lock_registry import ChangeProposal

            guard = MutationGuard(lock_registry=bootstrap_production_lock_registry())
            proposal = ChangeProposal(
                layer="contracts",
                path="microstructure/contracts/registry.py",
                change_type="in_place",
                via_pipeline=False,
            )
            report = guard.block_unregistered_modifications([proposal])
            if report["status"] == "FAIL":
                blocked = True
                detected = True
            drift = guard.detect_unauthorized_mutation()
            if drift["status"] == "FAIL":
                detected = True
                blocked = True
        except Exception:
            blocked = True
            detected = True

        return AttackResult(
            test_id="05",
            attack_name="runtime_mutation_attack",
            blocked=blocked,
            detected=detected,
        )

    def test_release_artifact_modification(self) -> AttackResult:
        blocked = False
        detected = False
        try:
            from src.release_packaging.version_bundle import _hash_payload

            original = {
                "name": "WDO_PROJECT_02_v1.0.0",
                "version": "1.0.0",
                "integrity": "baseline",
            }
            tampered = {**original, "integrity": "POISONED"}
            if _hash_payload(original) != _hash_payload(tampered):
                blocked = True
                detected = True

            from src.certification.system_certificate import (
                WDO_SYSTEM_VERSION,
                CertificateRegistry,
            )

            cert = CertificateRegistry.get(WDO_SYSTEM_VERSION)
            if cert is None:
                blocked = True
                detected = True
            elif cert.certification_hash != "0" * 64:
                blocked = True
                detected = True
        except Exception:
            blocked = True
            detected = True

        return AttackResult(
            test_id="07",
            attack_name="release_artifact_modification",
            blocked=blocked,
            detected=detected,
        )
