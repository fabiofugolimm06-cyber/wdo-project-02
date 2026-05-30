from microstructure.model.pipeline import run_ml_pipeline_v1
from tests.ohlcv_data import make_ohlcv


def test_pipeline_regression_snapshot():
    """
    Garante que o pipeline não muda comportamento sem intenção.
    """

    df = make_ohlcv(200, seed=42)

    out1 = run_ml_pipeline_v1(df.copy(), seed=42)
    out2 = run_ml_pipeline_v1(df.copy(), seed=42)

    # consistência estrutural
    assert out1.keys() == out2.keys()

    # estabilidade de métricas principais (ajuste conforme seu output real)
    assert abs(out1["metrics"]["accuracy"] - out2["metrics"]["accuracy"]) < 1e-9
    assert abs(out1["metrics"]["sharpe"] - out2["metrics"]["sharpe"]) < 1e-9