"""
CI — estabilidade do pipeline ML em 20 execuções (seed 42).
"""

from __future__ import annotations

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED
from microstructure.model.pipeline import pipeline_fingerprint
from tests.model_v1_pipeline import run_model_v1_integration_pipeline

_STRESS_RUNS = 20


def test_pipeline_is_stable_across_runs():
    expected_rows = 200 - 5
    base_fp = None

    for i in range(_STRESS_RUNS):
        out = run_model_v1_integration_pipeline(
            n_rows=200,
            seed=WDO_PROJECT_RANDOM_SEED,
        )
        assert out["n_ml"] == expected_rows, (
            f"run {i + 1}/{_STRESS_RUNS}: n_ml={out['n_ml']}, esperado {expected_rows}"
        )

        fp = pipeline_fingerprint(out)
        if base_fp is None:
            base_fp = fp
        else:
            assert fp == base_fp, f"run {i + 1}/{_STRESS_RUNS}: fingerprint divergiu"
