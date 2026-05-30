from microstructure.determinism import set_global_determinism
from tests.test_model_v1 import TestModelPipelineIntegration


def test_pipeline_is_stable_across_runs():
    results = []

    for _ in range(20):
        set_global_determinism(42)  # 🔥 FIX CRÍTICO

        test = TestModelPipelineIntegration()

        try:
            test.test_full_pipeline()
            results.append(1)
        except Exception:
            results.append(0)

    assert sum(results) / len(results) == 1.0