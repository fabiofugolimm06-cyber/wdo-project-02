"""
CI — stress de determinismo do pipeline ML crítico (≥10 execuções).
"""

from __future__ import annotations

import numpy as np
import pytest

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from tests.ohlcv_data import make_ohlcv

# Importa helper do módulo de testes do model (mesmo contrato do pipeline integrado)
from tests.test_model_v1 import _run_ml_pipeline

_STRESS_ITERATIONS = 10


@pytest.mark.ci_determinism
class TestCIDeterminismStress:
    def test_ml_pipeline_stable_10_iterations(self):
        """Detecta regressões de contagem (ex.: 176 vs 195) e métricas flutuantes."""
        df = make_ohlcv(200, seed=WDO_PROJECT_RANDOM_SEED)
        expected_rows = 200 - 5
        results = []

        for i in range(_STRESS_ITERATIONS):
            set_global_determinism(WDO_PROJECT_RANDOM_SEED)
            out = _run_ml_pipeline(df)
            assert out["n_ml"] == expected_rows, (
                f"iteração {i + 1}/{_STRESS_ITERATIONS}: n_ml={out['n_ml']}, "
                f"esperado {expected_rows}"
            )
            results.append(out)

        base = results[0]
        for i, out in enumerate(results[1:], start=2):
            assert out["n_ml"] == base["n_ml"], f"iteração {i}: shape divergente"
            assert out["metrics"] == base["metrics"], f"iteração {i}: métricas divergentes"
            assert np.array_equal(out["signals"], base["signals"]), (
                f"iteração {i}: sinais divergentes"
            )

    @pytest.mark.parametrize("run_idx", range(_STRESS_ITERATIONS))
    def test_full_pipeline_parametrized(self, run_idx: int):
        """Espelha TestModelPipelineIntegration::test_full_pipeline por iteração."""
        set_global_determinism(WDO_PROJECT_RANDOM_SEED)
        out = _run_ml_pipeline(make_ohlcv(200, seed=WDO_PROJECT_RANDOM_SEED))
        assert out["n_ml"] == 195
        assert out["n_train"] + out["n_test"] == out["n_ml"]
