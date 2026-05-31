"""
CI gate — mudanças de contrato devem passar por schema_diff sem breaking.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from microstructure.contracts.compatibility import validate_compatibility
from microstructure.contracts.contract_models import PipelineContract
from microstructure.contracts.schema_diff import diff_contracts
from microstructure.contracts import (
    full_pipeline_contract_v1,
    get_contract,
    ml_pipeline_contract_v1,
)
from microstructure.model.pipeline import run_ml_pipeline_v1
from microstructure.pipeline.end_to_end import run_full_pipeline
from tests.ohlcv_data import make_ohlcv

_BASELINES = (
    Path(__file__).resolve().parents[1]
    / "microstructure"
    / "contracts"
    / "baselines"
)


def _load_baseline(name: str) -> PipelineContract:
    path = _BASELINES / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return PipelineContract.from_dict(data)


def _assert_no_breaking(diff_label: str, baseline: PipelineContract, current: PipelineContract) -> None:
    diff = diff_contracts(baseline, current)
    assert not diff.breaking_changes, (
        f"{diff_label}: breaking contract change detectado.\n"
        f"removed_keys={sorted(diff.removed_keys)}\n"
        f"modified={list(diff.modified_constraints)}"
    )


class TestContractDiffCIGate:
    def test_registry_resolves_same_as_baseline_objects(self):
        assert get_contract("ml_pipeline:v1") is ml_pipeline_contract_v1
        assert get_contract("full_pipeline:v1") is full_pipeline_contract_v1

    def test_ml_contract_v1_matches_baseline_no_breaking(self):
        baseline = _load_baseline("ml_pipeline_contract_v1")
        _assert_no_breaking(
            "ml_pipeline_contract_v1",
            baseline,
            get_contract("ml_pipeline:v1"),
        )

    def test_full_pipeline_contract_v1_matches_baseline_no_breaking(self):
        baseline = _load_baseline("full_pipeline_contract_v1")
        _assert_no_breaking(
            "full_pipeline_contract_v1",
            baseline,
            full_pipeline_contract_v1,
        )

    def test_self_diff_is_empty(self):
        diff = diff_contracts(ml_pipeline_contract_v1, ml_pipeline_contract_v1)
        assert diff.added_keys == frozenset()
        assert diff.removed_keys == frozenset()
        assert diff.breaking_changes is False

    def test_removed_key_is_breaking(self):
        baseline = _load_baseline("ml_pipeline_contract_v1")
        mutated = PipelineContract(
            contract_id=baseline.contract_id,
            version=baseline.version,
            output_schema=dict(baseline.output_schema),
            required_top_keys=baseline.required_top_keys - {"proba"},
            forbidden_top_keys=baseline.forbidden_top_keys,
            nested_schemas=baseline.nested_schemas,
            allow_extra_top_keys=baseline.allow_extra_top_keys,
        )
        diff = diff_contracts(baseline, mutated)
        assert diff.breaking_changes is True
        assert "proba" in diff.removed_keys or any(
            "proba" in m for m in diff.modified_constraints
        )


class TestBackwardCompatibility:
    def test_ml_output_compatible_with_v1_contract(self):
        out = run_ml_pipeline_v1(make_ohlcv(120, seed=42), seed=42)
        validate_compatibility(ml_pipeline_contract_v1, out)

    def test_ml_output_rejects_silent_key_removal(self):
        out = run_ml_pipeline_v1(make_ohlcv(80, seed=42), seed=42)
        broken = {k: v for k, v in out.items() if k != "proba"}
        with pytest.raises(ValueError, match="remoção silenciosa|ausentes"):
            validate_compatibility(ml_pipeline_contract_v1, broken)

    def test_e2e_output_compatible_with_v1_contract(self):
        out = run_full_pipeline(make_ohlcv(250, seed=42), price_col="fechamento")
        validate_compatibility(full_pipeline_contract_v1, out)
