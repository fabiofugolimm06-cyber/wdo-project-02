import pytest
from tests.test_model_v1 import TestModelPipelineIntegration


def test_pipeline_is_stable_across_runs():
    test = TestModelPipelineIntegration()

    results = []
    for _ in range(20):
        try:
            test.test_full_pipeline()
            results.append(1)
        except Exception:
            results.append(0)

    success_rate = sum(results) / len(results)

    assert success_rate == 1.0, f"Pipeline instável: {success_rate*100:.1f}% sucesso"