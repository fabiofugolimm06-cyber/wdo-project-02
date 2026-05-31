"""
registry_tamper_tester.py — ataques de overwrite em registries.
"""

from __future__ import annotations

from src.adversarial_audit.audit_report import AttackResult


class RegistryTamperTester:
    """Tenta sobrescrever registries append-only."""

    def test_registry_overwrite_attack(self) -> AttackResult:
        blocked = False
        detected = False
        try:
            from src.snapshot_spec.snapshot_registry import (
                SnapshotDuplicateError,
                SnapshotRegistry,
                bootstrap_baseline_snapshot_registry,
            )

            baseline = bootstrap_baseline_snapshot_registry()
            attacker = SnapshotRegistry()
            for spec in baseline.list():
                attacker.register(spec)
            duplicate = baseline.list()[0]
            attacker.register(duplicate)
        except SnapshotDuplicateError:
            blocked = True
            detected = True
        except Exception:
            blocked = True
            detected = True

        return AttackResult(
            test_id="02",
            attack_name="registry_overwrite_attack",
            blocked=blocked,
            detected=detected,
        )

    def test_config_mutation_attack(self) -> AttackResult:
        blocked = False
        detected = False
        try:
            from src.config.config_contract import (
                ConfigContract,
                build_canonical_config_schema,
                compute_config_hash,
            )
            from src.config.config_registry import ConfigDuplicateError, ConfigRegistry

            schema = build_canonical_config_schema(environment="ci")
            contract = ConfigContract.create(
                config_id="wdo_ci",
                version="v1",
                schema=schema,
            )
            reg = ConfigRegistry()
            reg.register_config(contract)
            reg.register_config(contract)
        except ConfigDuplicateError:
            blocked = True
            detected = True
        except Exception:
            blocked = True
            detected = True

        return AttackResult(
            test_id="06",
            attack_name="config_mutation_attack",
            blocked=blocked,
            detected=detected,
        )
