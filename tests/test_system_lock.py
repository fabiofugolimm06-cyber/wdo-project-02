"""
tests/test_system_lock.py — System Lock Layer v1.
"""

from __future__ import annotations

import pytest

from src.system_lock import (
    ChangeProposal,
    LockRegistry,
    MutationGuard,
    SystemFreeze,
    bootstrap_production_lock_registry,
    classify_path,
    is_protected_path,
    validate_modification_path,
    validate_system_lock,
)


class TestProtectedPaths:
    def test_contracts_path_protected(self):
        assert classify_path("microstructure/contracts/registry.py") == "contracts"
        assert is_protected_path("src/ci/contract_ci_gate.py")

    def test_in_place_modification_blocked(self):
        report = validate_modification_path(
            "src/evolution/schema_version.py",
            change_type="in_place",
        )
        assert report["valid"] is False
        assert report["area"] == "evolution"

    def test_registry_append_via_pipeline_allowed(self):
        report = validate_modification_path(
            "src/contracts/data/data_contract.py",
            change_type="registry_append",
            via_pipeline=True,
        )
        assert report["valid"] is True


class TestSystemFreeze:
    def test_freeze_all_layers(self):
        registry = LockRegistry()
        result = SystemFreeze(lock_registry=registry).freeze_all()
        assert set(result["layers"]) == {
            "contracts",
            "data",
            "evolution",
            "snapshots",
        }
        assert len(result["system_fingerprint"]) == 64
        assert registry.validate_integrity()["valid"] is True


class TestMutationGuard:
    def test_no_mutation_after_freeze_passes(self):
        registry = bootstrap_production_lock_registry()
        report = MutationGuard(lock_registry=registry).detect_unauthorized_mutation()
        assert report["status"] == "PASS", report["failures"]

    def test_in_place_change_blocked(self):
        registry = bootstrap_production_lock_registry()
        guard = MutationGuard(lock_registry=registry)
        proposal = ChangeProposal(
            layer="contracts",
            path="microstructure/contracts/versions.py",
            change_type="in_place",
        )
        report = guard.validate_change_against_registry(proposal)
        assert report["status"] == "FAIL"

    def test_unauthorized_drift_detected(self):
        registry = bootstrap_production_lock_registry()
        frozen = registry.get_freeze("contracts")
        assert frozen is not None
        tampered = LockRegistry()
        tampered.register_freeze(frozen)
        tampered.set_system_fingerprint(registry.system_fingerprint or "")
        # fingerprint congelado desatualizado vs estado live
        report = MutationGuard(lock_registry=tampered).detect_unauthorized_mutation()
        assert report["status"] == "FAIL"

    def test_version_bump_via_pipeline_allowed(self):
        registry = bootstrap_production_lock_registry()
        guard = MutationGuard(lock_registry=registry)
        proposal = ChangeProposal(
            layer="evolution",
            path="src/evolution/evolution_registry.py",
            change_type="version_bump",
            from_version="v1",
            to_version="v2",
            via_pipeline=True,
        )
        record = guard.authorize_mutation(proposal)
        assert record is not None
        assert registry.has_authorized_mutation_for_layer("evolution")


class TestSystemLockCI:
    def test_validate_system_lock_passes(self):
        report = validate_system_lock()
        assert report["status"] == "PASS", report["failures"]

    def test_bootstrap_idempotent(self):
        r1 = bootstrap_production_lock_registry()
        r2 = bootstrap_production_lock_registry()
        assert r1.system_fingerprint == r2.system_fingerprint
