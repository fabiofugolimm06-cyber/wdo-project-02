"""
model_v1_pipeline.py — helper reutilizável do pipeline ML v1 (sem pytest).

Usado por testes de integração, stress de CI e determinismo.
"""

from __future__ import annotations

from typing import Any

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from microstructure.model.pipeline import run_ml_pipeline_v1
from tests.ohlcv_data import make_ohlcv


def run_model_v1_integration_pipeline(
    *,
    n_rows: int = 200,
    seed: int = WDO_PROJECT_RANDOM_SEED,
    horizon: int = 5,
    train_size: float = 0.70,
    ml_threshold: float = 0.55,
) -> dict[str, Any]:
    """
    Executa o pipeline ML v1 de ponta a ponta — determinístico, sem fixtures pytest.

    Equivalente funcional a ``TestModelPipelineIntegration.test_full_pipeline``.
    """
    set_global_determinism(seed)
    df = make_ohlcv(n_rows, seed=seed)
    out = run_ml_pipeline_v1(
        df,
        horizon=horizon,
        train_size=train_size,
        ml_threshold=ml_threshold,
        seed=seed,
    )

    expected_rows = n_rows - horizon
    assert out["n_ml"] == expected_rows, (
        f"n_ml={out['n_ml']}, esperado {expected_rows}"
    )
    assert out["n_train"] + out["n_test"] == out["n_ml"]
    assert out["proba"].shape[0] == out["n_test"]
    assert len(out["signals"]) == out["n_test"]

    return out
