"""
Regressão do pipeline ML v1 — contrato run_ml_pipeline_v1.
"""

from __future__ import annotations

from microstructure.contracts import assert_ml_pipeline_regression_stable
from microstructure.model.pipeline import run_ml_pipeline_v1
from tests.ohlcv_data import make_ohlcv


def test_pipeline_regression_snapshot():
    """Duas execuções com seed 42 devem ser idênticas (métricas ML apenas)."""
    df = make_ohlcv(200, seed=42)

    out1 = run_ml_pipeline_v1(df.copy(), seed=42)
    out2 = run_ml_pipeline_v1(df.copy(), seed=42)

    assert_ml_pipeline_regression_stable(out1, out2)
