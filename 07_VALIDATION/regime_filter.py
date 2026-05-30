import pandas as pd

def add_regime_filter(df: pd.DataFrame, atr_lookback: int = 20, threshold: float = 1.5) -> pd.DataFrame:
    df = df.copy()
    df['tr'] = df['máxima'] - df['mínima']
    df['atr'] = df['tr'].rolling(atr_lookback).mean()
    df['atr_ma'] = df['atr'].rolling(atr_lookback * 2).mean()
    df['regime_allowed'] = df['atr'] <= (df['atr_ma'] * threshold)
    df['regime_allowed'] = df['regime_allowed'].fillna(True)
    if 'posicao' in df.columns:
        df['posicao_original'] = df['posicao']
        df['posicao'] = df['posicao_original'].where(df['regime_allowed'], 0)
    return df