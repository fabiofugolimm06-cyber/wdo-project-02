"""
Pipeline completo WDO (v1):
    DATA → FEATURES → SIGNALS → BACKTEST

Uso:
    cd "WDO PROJECT 02"
    python -m microstructure.run_pipeline
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from microstructure.features.datasets import build_dataset
from microstructure.signal.signal_engine import generate_signals
from microstructure.backtest.engine_v1 import run_backtest


def _demo_ohlcv(n: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    idx = pd.date_range("2024-03-01 09:00", periods=n, freq="5min")
    close = 5200.0 + np.cumsum(rng.normal(0, 2, n))
    return pd.DataFrame(
        {
            "abertura": (close + rng.normal(0, 0.5, n)).astype("float32"),
            "fechamento": close.astype("float32"),
            "alta": (close + rng.uniform(1, 4, n)).astype("float32"),
            "baixa": (close - rng.uniform(1, 4, n)).astype("float32"),
            "volume": rng.integers(500, 3000, n).astype("float32"),
        },
        index=idx,
    )


def run_wdo_pipeline(df: pd.DataFrame, price_col: str = "fechamento") -> dict:
    """
    Executa pipeline end-to-end sem alterar módulos de features/signal.

    Parameters
    ----------
    df : OHLCV com DatetimeIndex (ex.: abertura, fechamento, alta, baixa, volume).
    price_col : coluna de preço para retorno futuro no backtest.

    Returns
    -------
    dict com chaves ``metrics``, ``df`` (backtest), ``X`` (features + signal).
    """
    X = build_dataset(df)
    X = generate_signals(X)

    # generate_signals retorna DataFrame; engine_v1 espera Series de sinais
    result = run_backtest(df, X["signal"], price_col=price_col)
    result["X"] = X
    return result


def main() -> None:
    df = _demo_ohlcv()
    out = run_wdo_pipeline(df, price_col="fechamento")
    print(out["metrics"])


if __name__ == "__main__":
    main()
