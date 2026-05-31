"""
tests/test_evolution_engine.py — Evolution Rule Engine v1.
"""

from __future__ import annotations

import copy

import pytest

from microstructure.contracts import get_contract, ml_pipeline_contract_v1
from microstructure.contracts.contract_models import PipelineContract
from src.evolution import (
    EvolutionRegistry,
    MigrationEngine,
    MigrationStep,
    SchemaStatus,
    SchemaVersion,
    bootstrap_pipeline_evolution_registry,
    compute_schema_hash,
    detect_contract_breaking_changes,
    detect_removed_fields,
)
from src.evolution.evolution_registry import (
    SchemaNotFoundError,
    SchemaVersionDuplicateError,
    validate_evolution_ci,
)
from src.evolution.migration_engine import MigrationError
from src.evolution.schema_version import SchemaVersionError


class TestSchemaVersion:
    def test_hash_deterministic(self):
        schema = {"type": "object", "required": ["a"]}
        h1 = compute_schema_hash(schema)
        h2 = compute_schema_hash(schema)
        assert h1 == h2
        sv = SchemaVersion.create(
            contract_id="test",
            version="v1",
            schema=schema,
        )
        assert sv.hash == h1

    def test_rejects_hash_override(self):
        schema = {"type": "object"}
        with pytest.raises(SchemaVersionError):
            SchemaVersion(
                contract_id="test",
                version="v1",
                parent_version=None,
                schema=schema,
                hash="0" * 64,
                status=SchemaStatus.ACTIVE,
            )

    def test_from_pipeline_contract(self):
        sv = SchemaVersion.from_pipeline_contract(
            ml_pipeline_contract_v1,
            contract_id="ml_pipeline",
            version="v1",
        )
        assert sv.contract_id == "ml_pipeline"
        assert sv.parent_version is None


class TestBreakingChangeDetector:
    def test_no_breaking_on_identical_contract(self):
        schema = ml_pipeline_contract_v1.to_dict()
        report = detect_contract_breaking_changes(schema, schema)
        assert report["breaking"] is False
        assert report["changes"] == []

    def test_detects_removed_top_key(self):
        old = ml_pipeline_contract_v1.to_dict()
        new = copy.deepcopy(old)
        new["required_top_keys"] = sorted(
            k for k in new["required_top_keys"] if k != "proba"
        )
        removed = detect_removed_fields(old, new)
        assert removed["breaking"] is True
        assert any("proba" in c for c in removed["changes"])

        report = detect_contract_breaking_changes(old, new)
        assert report["breaking"] is True


class TestEvolutionRegistry:
    def test_register_and_chain(self):
        reg = EvolutionRegistry()
        v1 = SchemaVersion.create(
            contract_id="demo",
            version="v1",
            schema={"required": ["a"]},
        )
        reg.register_version(v1)
        v2 = SchemaVersion.create(
            contract_id="demo",
            version="v2",
            schema={"required": ["a", "b"]},
            parent_version="v1",
            status=SchemaStatus.DEPRECATED,
        )
        reg.register_version(v2)
        assert reg.get_version("demo", "v2").parent_version == "v1"
        assert reg.validate_chain_integrity()["valid"] is True

    def test_rejects_multiple_active_versions(self):
        reg = EvolutionRegistry()
        reg.register_version(
            SchemaVersion.create(
                contract_id="demo",
                version="v1",
                schema={"required": ["a"]},
            )
        )
        reg.register_version(
            SchemaVersion.create(
                contract_id="demo",
                version="v2",
                schema={"required": ["a", "b"]},
                parent_version="v1",
            )
        )
        report = reg.validate_chain_integrity()
        assert report["valid"] is False
        assert any("múltiplas versões active" in e for e in report["errors"])

    def test_rejects_duplicate_version(self):
        reg = EvolutionRegistry()
        v1 = SchemaVersion.create(
            contract_id="demo",
            version="v1",
            schema={"required": ["a"]},
        )
        reg.register_version(v1)
        with pytest.raises(SchemaVersionDuplicateError):
            reg.register_version(v1)

    def test_bootstrap_pipeline_registry(self):
        reg = bootstrap_pipeline_evolution_registry()
        assert reg.validate_chain_integrity()["valid"] is True
        assert reg.get_version("ml_pipeline", "v1") is not None
        assert reg.get_version("full_pipeline", "v1") is not None


class TestMigrationEngine:
    def test_plan_and_execute_add_field(self):
        v1 = SchemaVersion.create(
            contract_id="demo",
            version="v1",
            schema={"required_top_keys": ["a"]},
        )
        v2 = SchemaVersion.create(
            contract_id="demo",
            version="v2",
            schema={"required_top_keys": ["a", "b"]},
            parent_version="v1",
        )
        engine = MigrationEngine()
        plan = engine.plan_migration(v1, v2)
        assert plan.breaking is False
        data = {"a": 1}
        migrated = engine.execute_migration_plan(data, plan)
        assert "b" in migrated
        rolled = engine.rollback_migration(migrated, plan)
        assert "b" not in rolled
        assert rolled == data

    def test_breaking_requires_explicit_steps(self):
        v1 = SchemaVersion.create(
            contract_id="demo",
            version="v1",
            schema=ml_pipeline_contract_v1.to_dict(),
        )
        broken = ml_pipeline_contract_v1.to_dict()
        broken["required_top_keys"] = sorted(
            k for k in broken["required_top_keys"] if k != "proba"
        )
        v2 = SchemaVersion.create(
            contract_id="demo",
            version="v2",
            schema=broken,
            parent_version="v1",
        )
        engine = MigrationEngine()
        with pytest.raises(MigrationError):
            engine.plan_migration(v1, v2)

        explicit = (
            MigrationStep(
                action="remove_field",
                path="proba",
                params={"previous_value": [], "explicit": True},
            ),
        )
        plan = engine.plan_migration(v1, v2, explicit_steps=explicit)
        assert plan.breaking is True
        assert plan.steps

    def test_validate_migration_path(self):
        reg = EvolutionRegistry()
        reg.register_version(
            SchemaVersion.create(
                contract_id="demo",
                version="v1",
                schema={"x": 1},
            )
        )
        reg.register_version(
            SchemaVersion.create(
                contract_id="demo",
                version="v2",
                schema={"x": 1, "y": 2},
                parent_version="v1",
            )
        )
        report = MigrationEngine().validate_migration_path(
            reg, "demo", "v1", "v2"
        )
        assert report["valid"] is True
        assert report["path"] == ["v1", "v2"]


class TestEvolutionCI:
    def test_validate_evolution_ci_passes(self):
        reg = bootstrap_pipeline_evolution_registry()
        report = validate_evolution_ci(reg)
        assert report["status"] == "PASS", report["failures"]

    def test_ci_fails_on_broken_chain_without_migration(self):
        reg = EvolutionRegistry()
        reg.register_version(
            SchemaVersion.from_pipeline_contract(
                ml_pipeline_contract_v1,
                contract_id="ml_pipeline",
                version="v1",
            )
        )
        broken = ml_pipeline_contract_v1.to_dict()
        broken["required_top_keys"] = sorted(
            k for k in broken["required_top_keys"] if k != "proba"
        )
        mutated = PipelineContract.from_dict(broken)
        reg.register_version(
            SchemaVersion.from_pipeline_contract(
                mutated,
                contract_id="ml_pipeline",
                version="v2",
                parent_version="v1",
            )
        )
        report = validate_evolution_ci(reg)
        assert report["status"] == "FAIL"
        assert report["failures"]

    def test_get_version_latest(self):
        reg = bootstrap_pipeline_evolution_registry()
        latest = reg.get_version("ml_pipeline")
        assert latest.version == "v1"

    def test_get_version_not_found(self):
        reg = EvolutionRegistry()
        with pytest.raises(SchemaNotFoundError):
            reg.get_version("missing")
