"""
regime_classifier.py
WDO-EVOLVED-QUANT | Fase 2 — Módulo M2
Versão: 1.0 | Data: 27/05/2026

Adiciona 3 colunas de regime ao DataFrame sem modificar nenhuma coluna existente:

  vol_regime     : LOW / MID / HIGH
                   ATR(14) classificado por percentil rolling de 100 barras.
                   Sem look-ahead: percentil calculado apenas com histórico.

  trend_regime   : TREND_UP / TREND_DOWN / RANGE
                   Diferença EMA(8) - EMA(21) normalizada pelo ATR.
                   Threshold de 0.15 × ATR para declarar tendência.

  session_regime : OPENING / CORE / CLOSING
                   Baseado na hora do pregão WDO (fuso Brasília, GMT-3):
                     OPENING  → antes de 10:30 (descoberta de preço)
                     CORE     → 10:30 a 15:30  (fluxo principal)
                     CLOSING  → após 15:30      (squaring de posições)

Nomes de coluna esperados: fechamento, máxima, mínima, datetime
(padrão português do pipeline WDO-EVOLVED-QUANT)

Uso:
    from regime_classifier import classify_regime
    df = classify_regime(df)   # adiciona as 3 colunas, retorna cópia
"""

import pandas as pd
import numpy as np

# ── Parâmetros (documentar, não otimizar) ────────────────────────────────────
_ATR_PERIOD       = 14    # período do Average True Range
_ATR_PERCENTILE_N = 100   # janela do percentil para vol_regime
_EMA_FAST         = 8     # EMA rápida (trend_regime)
_EMA_SLOW         = 21    # EMA lenta  (trend_regime)
_TREND_THRESHOLD  = 0.15  # diferença EMA / ATR mínima para declarar tendência

# Limites de sessão em minutos desde meia-noite (fuso Brasília)
_OPENING_END_MIN  = 10 * 60 + 30   # 10:30
_CLOSING_START_MIN = 15 * 60 + 30  # 15:30


# ── Ponto de entrada público ─────────────────────────────────────────────────

def classify_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe o DataFrame do pipeline (qualquer estado pós-carga) e retorna
    uma cópia com as colunas vol_regime, trend_regime e session_regime.

    Não modifica o DataFrame original.
    Não remove nem renomeia colunas existentes.
    """
    df = df.copy()
    _add_vol_regime(df)
    _add_trend_regime(df)
    _add_session_regime(df)
    return df


# ── Implementações privadas ──────────────────────────────────────────────────

def _true_range(df: pd.DataFrame) -> pd.Series:
    """True Range: max(H-L, |H-Cp|, |L-Cp|). Reutilizado por vol e trend."""
    prev_close = df["fechamento"].shift(1)
    return pd.concat(
        [
            df["máxima"] - df["mínima"],
            (df["máxima"] - prev_close).abs(),
            (df["mínima"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _add_vol_regime(df: pd.DataFrame) -> None:
    """
    vol_regime: LOW / MID / HIGH

    ATR(14) calculado para cada barra. Classificado pelo percentil dentro
    de uma janela rolling de 100 barras — sem look-ahead:
      pct < 0.33 → LOW  (volatilidade historicamente baixa)
      pct > 0.67 → HIGH (volatilidade historicamente alta)
      else       → MID
    """
    atr = _true_range(df).rolling(_ATR_PERIOD, min_periods=_ATR_PERIOD).mean()

    # rank(pct=True) dentro da janela → percentil local sem look-ahead
    atr_pct = atr.rolling(_ATR_PERCENTILE_N, min_periods=_ATR_PERIOD).rank(pct=True)

    df["vol_regime"] = "MID"
    df.loc[atr_pct <  0.33, "vol_regime"] = "LOW"
    df.loc[atr_pct >= 0.67, "vol_regime"] = "HIGH"


def _add_trend_regime(df: pd.DataFrame) -> None:
    """
    trend_regime: TREND_UP / TREND_DOWN / RANGE

    (EMA_fast - EMA_slow) / ATR normaliza a diferença de EMAs pelo nível
    de volatilidade atual, tornando o threshold invariante ao preço:
      diff / ATR >  _TREND_THRESHOLD → TREND_UP
      diff / ATR < -_TREND_THRESHOLD → TREND_DOWN
      |diff / ATR| <= _TREND_THRESHOLD → RANGE
    """
    ema_fast = df["fechamento"].ewm(span=_EMA_FAST, adjust=False).mean()
    ema_slow = df["fechamento"].ewm(span=_EMA_SLOW, adjust=False).mean()

    atr = _true_range(df).rolling(_ATR_PERIOD, min_periods=_ATR_PERIOD).mean()

    diff_norm = (ema_fast - ema_slow) / (atr + 1e-9)

    df["trend_regime"] = "RANGE"
    df.loc[diff_norm >  _TREND_THRESHOLD, "trend_regime"] = "TREND_UP"
    df.loc[diff_norm < -_TREND_THRESHOLD, "trend_regime"] = "TREND_DOWN"


def _add_session_regime(df: pd.DataFrame) -> None:
    """
    session_regime: OPENING / CORE / CLOSING

    Baseado apenas na hora do pregão — sem lógica de calendário de feriados.
    Ajuste o fuso se os dados estiverem em UTC.

    Pregão WDO Bovespa (horário de Brasília):
      OPENING : abertura até 10:30 → descoberta de preço, maior volatilidade
      CORE    : 10:30 a 15:30     → fluxo principal, liquidez máxima
      CLOSING : após 15:30        → squaring de posições, volatilidade crescente
    """
    time_min = df["datetime"].dt.hour * 60 + df["datetime"].dt.minute

    df["session_regime"] = "CORE"
    df.loc[time_min <  _OPENING_END_MIN,   "session_regime"] = "OPENING"
    df.loc[time_min >= _CLOSING_START_MIN, "session_regime"] = "CLOSING"
