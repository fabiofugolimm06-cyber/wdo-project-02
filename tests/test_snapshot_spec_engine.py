"""
tests/test_snapshot_spec_engine.py — Snapshot-as-Spec Engine v1.
"""

from __future__ import annotations

import copy

import pytest

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED
from src.snapshot_spec import (
    SnapshotCIGate,
    SnapshotDiffEngine,
    SnapshotDuplicateError,
    SnapshotRegistry,
    SnapshotSpec,
    SnapshotValidator,
    bootstrap_baseline_snapshot_registry,
    compute_state_hash,
)


class TestSnapshotSpec:
    def test_state_hash_deterministic(self):
        structure = {"schema": {"a": 1}, "structure": {"n": 1}}
        metrics = {"accuracy": 0.5}
        h1 = compute_state_hash(
            contract_id="ml_pipeline_contract_v1",
            pipeline_stage="ml",
            structure=structure,
            metrics=metrics,
            deterministic_seed=42,
        )
        h2 = compute_state_hash(
            contract_id="ml_pipeline_contract_v1",
            pipeline_stage="ml",
            structure=structure,
            metrics=metrics,
            deterministic_seed=42,
        )
        assert h1 == h2

    def test_from_baseline_ml_snapshot(self):
        reg = bootstrap_baseline_snapshot_registry()
        spec = reg.get("ml_pipeline_v1_seed42")
        assert spec.pipeline_stage == "ml"
        assert spec.deterministic_seed == WDO_PROJECT_RANDOM_SEED
        assert len(spec.state_hash) == 64


class TestSnapshotRegistry:
    def test_bootstrap_and_integrity(self):
        reg = bootstrap_baseline_snapshot_registry()
        assert reg.validate_registry_integrity()["valid"] is True
        assert len(reg.list()) == 2

    def test_rejects_duplicate_id(self):
        reg = bootstrap_baseline_snapshot_registry()
        spec = reg.get("ml_pipeline_v1_seed42")
        with pytest.raises(SnapshotDuplicateError):
            reg.register(spec)


class TestSnapshotDiffEngine:
    def test_no_drift_on_identical_specs(self):
        reg = bootstrap_baseline_snapshot_registry()
        spec = reg.get("ml_pipeline_v1_seed42")
        diff = SnapshotDiffEngine().diff(spec, spec)
        assert diff["breaking"] is False
        assert diff["changes"] == []

    def test_structural_drift_is_breaking(self):
        reg = bootstrap_baseline_snapshot_registry()
        base = reg.get("ml_pipeline_v1_seed42")
        structure = copy.deepcopy(base.structure)
        structure["structure"] = {**structure["structure"], "n_ml": 999}
        mutated = SnapshotSpec(
            snapshot_id="mutated",
            contract_id=base.contract_id,
            pipeline_stage=base.pipeline_stage,
            state_hash=compute_state_hash(
                contract_id=base.contract_id,
                pipeline_stage=base.pipeline_stage,
                structure=structure,
                metrics=base.metrics,
                deterministic_seed=base.deterministic_seed,
            ),
            structure=structure,
            metrics=base.metrics,
            deterministic_seed=base.deterministic_seed,
        )
        report = SnapshotDiffEngine().detect_structural_drift(base, mutated)
        assert report["breaking"] is True


class TestSnapshotValidator:
    def test_validate_baseline_passes(self):
        reg = bootstrap_baseline_snapshot_registry()
        validator = SnapshotValidator()
        for spec in reg.list():
            report = validator.validate(spec)
            assert report["status"] == "PASS", report["failures"]

    def test_validate_determinism_20_runs(self):
        reg = bootstrap_baseline_snapshot_registry()
        spec = reg.get("ml_pipeline_v1_seed42")
        report = SnapshotValidator().validate_determinism(spec, snapshot_runs=20)
        assert report["status"] == "PASS", report["failures"]


class TestSnapshotSpecCIGate:
    def test_run_full_snapshot_spec_check_passes(self):
        report = SnapshotCIGate().run_full_snapshot_spec_check()
        assert report["status"] == "PASS", report["failures"]

    def test_list_by_contract_id(self):
        reg = bootstrap_baseline_snapshot_registry()
        ml_specs = reg.list("ml_pipeline_contract_v1")
        assert len(ml_specs) == 1
