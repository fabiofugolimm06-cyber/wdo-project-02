"""
tests/ohlcv_data.py — OHLCV sintético determinístico (compartilhado entre testes).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED


def make_ohlcv(
    n: int = 200,
    seed: int = WDO_PROJECT_RANDOM_SEED,
    start: str = "2024-01-01",
) -> pd.DataFrame:
    """
    Gera OHLCV com ``numpy.random.default_rng(seed)`` — nunca RNG sem seed.

    Retorna cópia independente a cada chamada (mesmo seed → mesmo conteúdo).
    """
    if n < 1:
        raise ValueError(f"make_ohlcv: n deve ser >= 1, got {n}.")

    rng = np.random.default_rng(int(seed))
    idx = pd.date_range(start, periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    fechamento = price.astype(np.float32)
    return pd.DataFrame(
        {
            "abertura": fechamento.copy(),
            "alta": (fechamento + 1).astype(np.float32),
            "baixa": (fechamento - 1).astype(np.float32),
            "fechamento": fechamento,
            "volume": rng.integers(100, 1000, n).astype(np.float32),
        },
        index=idx,
    )
