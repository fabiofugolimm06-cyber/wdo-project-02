"""
event_classifier.py
WDO-EVOLVED-QUANT | Fase 2 — Módulo M1
Versão: 1.0 | Data: 27/05/2026

Classifica cada barra do DataFrame em um tipo estrutural de evento:
  INITIATION  — range expandido + corpo direcional forte → players tomando posição
  ABSORPTION  — range expandido + corpo pequeno → liquidez absorvida sem mover preço
  EXHAUSTION  — range expandido + reversão de momentum → última onda de um movimento
  NONE        — barra sem evento estrutural relevante

Nomes de coluna: português (padrão do pipeline WDO-EVOLVED-QUANT)
  abertura  = open
  fechamento = close
  máxima     = high
  mínima     = low
"""

import pandas as pd
import numpy as np


def classify_event(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona coluna 'event_type' com classificação estrutural de cada barra.

    Parâmetros de classificação (sem otimização — apenas medição):
      vol_ratio  > 1.5  : range da barra >= 1.5x a média das últimas 20
      body_ratio > 0.30 : corpo >= 30% do range → direção definida (INITIATION)
      body_ratio < 0.20 : corpo <= 20% do range → sem direção clara (ABSORPTION)
      vol_ratio  > 1.8  : range >= 1.8x + reversão de momentum (EXHAUSTION)

    Colunas requeridas: abertura, fechamento, máxima, mínima
    Colunas adicionadas: range, body, body_ratio, vol_ma, vol_ratio, momentum, event_type
    """
    df = df.copy()

    # ── Features de morfologia de vela ─────────────────────────────────────────
    df["range"]      = df["máxima"]    - df["mínima"]
    df["body"]       = df["fechamento"] - df["abertura"]
    df["body_ratio"] = df["body"] / (df["range"] + 1e-9)

    # ── Range relativo ao histórico (proxy de expansão de liquidez) ─────────────
    df["vol_ma"]    = df["range"].rolling(20, min_periods=20).mean()
    df["vol_ratio"] = df["range"] / (df["vol_ma"] + 1e-9)

    # ── Momentum de preço (reversão = exaustão) ─────────────────────────────────
    df["momentum"] = df["fechamento"].diff(3)

    # ── Classificação (ordem importa: EXHAUSTION sobrescreve INITIATION) ────────
    df["event_type"] = "NONE"

    # INITIATION: expansão de range + corpo direcional forte
    df.loc[
        (df["vol_ratio"]        > 1.5) &
        (df["body_ratio"].abs() > 0.30) &
        (df["momentum"].abs()   > 0),
        "event_type",
    ] = "INITIATION"

    # ABSORPTION: expansão de range + corpo minúsculo (volume sem movimento)
    df.loc[
        (df["vol_ratio"]        > 1.5) &
        (df["body_ratio"].abs() < 0.20),
        "event_type",
    ] = "ABSORPTION"

    # EXHAUSTION: expansão forte + inversão de momentum de 3 barras
    df.loc[
        (df["vol_ratio"]         > 1.8) &
        (df["momentum"].shift(1) > 0) &
        (df["momentum"]          < 0),
        "event_type",
    ] = "EXHAUSTION"

    return df
