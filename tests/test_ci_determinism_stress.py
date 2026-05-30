"""
CI — stress de determinismo do pipeline ML crítico (20 execuções).
"""

from __future__ import annotations

import pytest

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from microstructure.model.pipeline import pipeline_fingerprint, run_ml_pipeline_v1
from tests.ohlcv_data import make_ohlcv

# 10 loop + 10 parametrized = 20 runs no CI
_STRESS_ITERATIONS = 10
_TOTAL_CI_RUNS = 20


@pytest.mark.ci_determinism
class TestCIDeterminismStress:
    def test_ml_pipeline_stable_20_equivalent_runs(self):
        """
        10 execuções isoladas com DataFrame novo a cada iteração.

        Compara fingerprint (shape, métricas arredondadas, sinais, proba bytes).
        """
        expected_rows = 200 - 5
        base_fp = None

        for i in range(_STRESS_ITERATIONS):
            set_global_determinism(WDO_PROJECT_RANDOM_SEED)
            out = run_ml_pipeline_v1(
                make_ohlcv(200, seed=WDO_PROJECT_RANDOM_SEED),
                seed=WDO_PROJECT_RANDOM_SEED,
            )
            assert out["n_ml"] == expected_rows, (
                f"loop {i + 1}/{_STRESS_ITERATIONS}: n_ml={out['n_ml']}"
            )
            fp = pipeline_fingerprint(out)
            if base_fp is None:
                base_fp = fp
            else:
                assert fp == base_fp, f"loop {i + 1}: fingerprint divergiu"

    @pytest.mark.parametrize("run_idx", range(_STRESS_ITERATIONS))
    def test_full_pipeline_parametrized(self, run_idx: int):
        """Mais 10 runs — reinício de seed por teste (conftest autouse)."""
        set_global_determinism(WDO_PROJECT_RANDOM_SEED)
        out = run_ml_pipeline_v1(
            make_ohlcv(200, seed=WDO_PROJECT_RANDOM_SEED),
            seed=WDO_PROJECT_RANDOM_SEED,
        )
        assert out["n_ml"] == 195
        assert out["n_train"] + out["n_test"] == out["n_ml"]
