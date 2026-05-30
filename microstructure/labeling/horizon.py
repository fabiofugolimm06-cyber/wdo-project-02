"""
microstructure/labeling/horizon.py — Horizon labels (direção do retorno futuro).
"""

from __future__ import annotations

import pandas as pd

from microstructure.labeling.utils import validate_price_series


def create_horizon_labels(
    df: pd.DataFrame,
    price_col: str = "fechamento",
    horizon: int = 5,
) -> pd.Series:
    """
    Label binário por horizonte fixo (causal em X, alvo usa apenas preço futuro).

    Definição
    ---------
    future_return[t] = price[t + horizon] / price[t] - 1

    y[t] = 1  se future_return[t] > 0
    y[t] = 0  caso contrário (inclui retorno zero)

    Anti-leakage
    ------------
    - ``y[t]`` depende apenas de preços em t e t+horizon (nunca de t-1 para features).
    - Últimas ``horizon`` barras ficam com NaN (sem preço futuro observável).
    - Features em ``X[t]`` não devem usar ``shift(-k)`` com k > 0.

    Parameters
    ----------
    df : OHLCV com DatetimeIndex.
    price_col : coluna de preço (WDO: ``fechamento``).
    horizon : barras à frente para calcular o retorno.

    Returns
    -------
    pd.Series ``y`` (Int8 nullable), índice igual a ``df``, nome ``label_horizon_{h}``.
    """
    if horizon < 1:
        raise ValueError(f"create_horizon_labels: horizon deve ser >= 1, got {horizon}.")

    work = df.copy()
    price = validate_price_series(work, price_col)

    # Preço futuro causal: shift negativo olha horizon barras à frente
    future_price = price.shift(-horizon)
    future_return = future_price / price - 1.0

    y = (future_return > 0).astype("Int8")
    y[future_return.isna()] = pd.NA

    y.name = f"label_horizon_{horizon}"
    return y
