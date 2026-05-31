"""
Contract Enforcement Engine — validação imediata ML vs E2E.
"""

from __future__ import annotations

import pytest

from microstructure.contracts.compatibility import (
    assert_ml_pipeline_regression_stable,
    get_backtest_metrics_block,
    get_model_metrics_block,
    resolve_regression_metric,
)
from microstructure.contracts.enforcement import (
    ContractViolationError,
    validate_full_pipeline_contract,
    validate_ml_contract,
)
from microstructure.contracts.versions import ml_pipeline_contract_v1
from microstructure.model.pipeline import run_ml_pipeline_v1
from microstructure.pipeline.end_to_end import run_full_pipeline
from tests.ohlcv_data import make_ohlcv


def test_validate_ml_contract_accepts_pipeline_output():
    out = run_ml_pipeline_v1(make_ohlcv(100, seed=42), seed=42)
    validate_ml_contract(out)


def test_validate_ml_contract_rejects_sharpe_in_metrics():
    out = run_ml_pipeline_v1(make_ohlcv(80, seed=42), seed=42)
    bad = dict(out)
    bad["metrics"] = {**out["metrics"], "sharpe": 1.5}
    with pytest.raises(ContractViolationError, match="sharpe|backtest|proibidas"):
        validate_ml_contract(bad)


def test_validate_ml_contract_rejects_e2e_top_level_block():
    out = run_ml_pipeline_v1(make_ohlcv(80, seed=42), seed=42)
    bad = dict(out)
    bad["backtest_metrics"] = {"sharpe": 0.0}
    with pytest.raises(ContractViolationError, match="E2E"):
        validate_ml_contract(bad)


def test_validate_full_pipeline_contract_accepts_e2e_output():
    out = run_full_pipeline(make_ohlcv(200, seed=42), price_col="fechamento")
    validate_full_pipeline_contract(out)
    assert "sharpe" in out["backtest_metrics"]
    assert "sharpe" not in out["model_metrics"]


def test_validate_full_pipeline_contract_rejects_sharpe_in_model_metrics():
    out = run_full_pipeline(make_ohlcv(180, seed=42), price_col="fechamento")
    bad = dict(out)
    bad["model_metrics"] = {**out["model_metrics"], "sharpe": 2.0}
    with pytest.raises(ContractViolationError, match="sharpe|backtest"):
        validate_full_pipeline_contract(bad)


def test_enforcement_matches_contract_required_keys():
    out = run_ml_pipeline_v1(make_ohlcv(90, seed=42), seed=42)
    validate_ml_contract(out)
    assert frozenset(out.keys()) == ml_pipeline_contract_v1.required_top_keys


def test_get_model_metrics_block_ml_and_e2e():
    ml = run_ml_pipeline_v1(make_ohlcv(80, seed=42), seed=42)
    e2e = run_full_pipeline(make_ohlcv(120, seed=42), price_col="fechamento")
    assert get_model_metrics_block(ml) is ml["metrics"]
    assert get_model_metrics_block(e2e) is e2e["model_metrics"]


def test_resolve_regression_metric_sharpe_requires_e2e():
    ml = run_ml_pipeline_v1(make_ohlcv(80, seed=42), seed=42)
    with pytest.raises(KeyError, match="backtest_metrics"):
        resolve_regression_metric(ml, "sharpe")

    e2e = run_full_pipeline(make_ohlcv(120, seed=42), price_col="fechamento")
    assert resolve_regression_metric(e2e, "sharpe") == pytest.approx(
        float(e2e["backtest_metrics"]["sharpe"])
    )
    assert resolve_regression_metric(ml, "accuracy") == pytest.approx(
        float(ml["metrics"]["accuracy"])
    )


def test_assert_ml_pipeline_regression_stable():
    df = make_ohlcv(100, seed=42)
    out1 = run_ml_pipeline_v1(df.copy(), seed=42)
    out2 = run_ml_pipeline_v1(df.copy(), seed=42)
    assert_ml_pipeline_regression_stable(out1, out2)
