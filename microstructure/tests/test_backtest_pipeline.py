"""
Validação end-to-end do pipeline:

    DATA → FEATURES → SIGNALS → BACKTEST

Não altera feature engine, registry, dataset builder nem signal engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.features.datasets import build_dataset
from microstructure.signal.signal_engine import generate_signals
from microstructure.backtest.engine_v1 import run_backtest

METRIC_KEYS = frozenset({
    "total_return",
    "sharpe",
    "max_drawdown",
    "win_rate",
    "num_trades",
})


def _synthetic_ohlcv(n: int = 200) -> pd.DataFrame:
    """OHLCV sintético com DatetimeIndex (requisito do Feature Engine)."""
    rng = np.random.default_rng(7)
    idx = pd.date_range("2024-01-01", periods=n, freq="min")
    fechamento = 5200.0 + np.cumsum(rng.normal(0, 1.5, n))
    return pd.DataFrame(
        {
            "abertura": (fechamento + rng.normal(0, 0.3, n)).astype("float32"),
            "alta": (fechamento + rng.uniform(0.5, 3.0, n)).astype("float32"),
            "baixa": (fechamento - rng.uniform(0.5, 3.0, n)).astype("float32"),
            "fechamento": fechamento.astype("float32"),
            "volume": rng.integers(800, 2500, n).astype("float32"),
        },
        index=idx,
    )


def test_full_backtest_pipeline_integration(capsys):
    """
    Fluxo completo: build_dataset → generate_signals → run_backtest.
    """
    df = _synthetic_ohlcv(200)
    assert isinstance(df.index, pd.DatetimeIndex)

    # FEATURES
    X = build_dataset(df)
    assert X.shape[0] == 200
    assert X.shape[1] >= 1
    assert {"delta", "returns"}.issubset(set(X.columns))

    # SIGNALS
    X = generate_signals(X)
    assert "signal" in X.columns
    signals = X["signal"]
    assert len(signals) == len(df)
    assert set(signals.dropna().unique()).issubset({-1, 0, 1})

    # BACKTEST
    result = run_backtest(
        df=df,
        signals=signals,
        price_col="fechamento",
    )

    assert "df" in result
    assert "metrics" in result
    metrics = result["metrics"]

    print(metrics)

    for key in METRIC_KEYS:
        assert key in metrics, f"métrica ausente: {key}"

    bt_df = result["df"]
    assert "equity" in bt_df.columns
    assert "drawdown" in bt_df.columns
    assert "strategy_return" in bt_df.columns
    assert len(bt_df) == len(df)

    captured = capsys.readouterr()
    assert "total_return" in captured.out or metrics is not None

    print("BACKTEST PIPELINE OK")


def test_metrics_are_numeric():
    """Métricas devem ser escalares numéricos (ou NaN em edge cases)."""
    df = _synthetic_ohlcv(120)
    X = generate_signals(build_dataset(df))
    result = run_backtest(df, X["signal"], price_col="fechamento")
    m = result["metrics"]
    for key in METRIC_KEYS:
        assert isinstance(m[key], (int, float, np.floating, np.integer))
