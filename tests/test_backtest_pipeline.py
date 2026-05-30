"""
Validação oficial do pipeline:

    DATA → FEATURES → SIGNALS → BACKTEST

Série de preços sintética economicamente plausível (sempre positiva).

Executar na raiz do projeto:

    python -m pytest tests/test_backtest_pipeline.py -v -s
"""

import pandas as pd
import numpy as np

from microstructure.features.datasets import build_dataset
from microstructure.signal.signal_engine import generate_signals
from microstructure.backtest.engine_v1 import run_backtest


def _synthetic_ohlcv_plausible(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """OHLCV com preços positivos e relação alta >= max(o,c), baixa <= min(o,c)."""
    rng = np.random.default_rng(seed)

    idx = pd.date_range("2024-01-01", periods=n, freq="min")

    price = 100 + np.cumsum(
        rng.normal(loc=0, scale=0.5, size=n)
    )

    fechamento = price.astype(np.float32)
    abertura = (fechamento + rng.normal(0, 0.1, n)).astype(np.float32)
    alta = (
        np.maximum(abertura, fechamento)
        + np.abs(rng.normal(0, 0.1, n))
    ).astype(np.float32)
    baixa = (
        np.minimum(abertura, fechamento)
        - np.abs(rng.normal(0, 0.1, n))
    ).astype(np.float32)
    volume = rng.integers(100, 1000, size=n).astype(np.float32)

    df = pd.DataFrame(
        {
            "abertura": abertura,
            "alta": alta,
            "baixa": baixa,
            "fechamento": fechamento,
            "volume": volume,
        },
        index=idx,
    )

    assert (df[["abertura", "alta", "baixa", "fechamento"]] > 0).all().all()
    assert (df["alta"] >= df[["abertura", "fechamento"]].max(axis=1)).all()
    assert (df["baixa"] <= df[["abertura", "fechamento"]].min(axis=1)).all()

    return df


def test_backtest_pipeline_integration(capsys):
    df = _synthetic_ohlcv_plausible(200)

    X = build_dataset(df)
    X = generate_signals(X)
    signals = X["signal"]

    result = run_backtest(
        df=df,
        signals=signals,
        price_col="fechamento",
    )

    metrics = result["metrics"]
    bt = result["df"]

    print(metrics)

    assert "total_return" in metrics
    assert "sharpe" in metrics
    assert "max_drawdown" in metrics
    assert "win_rate" in metrics
    assert "num_trades" in metrics

    # Sanity: métricas economicamente interpretáveis
    assert np.isfinite(metrics["total_return"])
    assert abs(metrics["total_return"]) < 5.0, (
        f"total_return fora de faixa plausível: {metrics['total_return']}"
    )

    assert -1.0 <= metrics["max_drawdown"] <= 0.0, (
        f"max_drawdown deve estar em [-1, 0], got {metrics['max_drawdown']}"
    )

    equity = bt["equity"].dropna()
    assert len(equity) > 0
    assert np.isfinite(equity).all()
    assert (equity > 0).all(), "equity curve deve permanecer positiva"
    assert equity.std() > 0, "equity deve variar (não constante degenerada)"

    assert 0.0 <= metrics["win_rate"] <= 1.0
    assert metrics["num_trades"] >= 0

    print("BACKTEST PIPELINE OK")
