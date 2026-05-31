"""
Snapshot estrutural dos pipelines v1 (ML + E2E, seed 42).

- Schema drift → ALWAYS FAIL
- Métricas numéricas → tolerância epsilon
"""

from __future__ import annotations

from pathlib import Path

import pytest

from microstructure.contracts.snapshot import (
    DEFAULT_NUMERIC_EPSILON,
    build_full_pipeline_snapshot,
    build_ml_pipeline_snapshot,
    compare_pipeline_snapshots,
    load_snapshot,
)
from microstructure.contracts.versions import (
    full_pipeline_contract_v1,
    ml_pipeline_contract_v1,
)
from microstructure.contracts.compatibility import validate_compatibility
from microstructure.contracts.enforcement import (
    validate_full_pipeline_contract,
    validate_ml_contract,
)
from microstructure.model.pipeline import run_ml_pipeline_v1
from microstructure.pipeline.end_to_end import run_full_pipeline
from tests.ohlcv_data import make_ohlcv

_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
_ML_SNAPSHOT = _SNAPSHOTS / "ml_pipeline_v1_seed42.json"
_E2E_SNAPSHOT = _SNAPSHOTS / "full_pipeline_v1_seed42.json"

_SEED = 42
_N_BARS_ML = 200
_N_BARS_E2E = 300

pytestmark = pytest.mark.slow


def test_ml_pipeline_snapshot_v1_matches_stored():
    out = run_ml_pipeline_v1(make_ohlcv(_N_BARS_ML, seed=_SEED), seed=_SEED)
    validate_ml_contract(out)
    validate_compatibility(ml_pipeline_contract_v1, out)

    actual = build_ml_pipeline_snapshot(
        out,
        contract_id=ml_pipeline_contract_v1.contract_id,
        contract_version=ml_pipeline_contract_v1.version,
    )
    expected = load_snapshot(_ML_SNAPSHOT)

    errors = compare_pipeline_snapshots(
        actual,
        expected,
        epsilon=DEFAULT_NUMERIC_EPSILON,
    )
    assert errors == [], "ML snapshot drift:\n" + "\n".join(errors)


def test_full_pipeline_snapshot_v1_matches_stored():
    out = run_full_pipeline(
        make_ohlcv(_N_BARS_E2E, seed=_SEED),
        price_col="fechamento",
    )
    validate_full_pipeline_contract(out)
    validate_compatibility(full_pipeline_contract_v1, out)

    actual = build_full_pipeline_snapshot(
        out,
        contract_id=full_pipeline_contract_v1.contract_id,
        contract_version=full_pipeline_contract_v1.version,
    )
    expected = load_snapshot(_E2E_SNAPSHOT)

    errors = compare_pipeline_snapshots(
        actual,
        expected,
        epsilon=DEFAULT_NUMERIC_EPSILON,
    )
    assert errors == [], "E2E snapshot drift:\n" + "\n".join(errors)


def test_snapshot_detects_schema_drift():
    expected = load_snapshot(_ML_SNAPSHOT)
    broken = dict(expected)
    broken["schema"] = {
        **expected["schema"],
        "top_keys": sorted(expected["schema"]["top_keys"]) + ["extra_key"],
    }
    errors = compare_pipeline_snapshots(broken, expected)
    assert any("schema drift" in e for e in errors)
