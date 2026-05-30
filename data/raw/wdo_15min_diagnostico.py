"""
wdo_15min_diagnostico.py - Diagnóstico para encontrar trades
"""

import pandas as pd
import numpy as np
from pathlib import Path

INPUT_CSV = r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_OHLC.csv"

def load_data():
    print("📂 Lendo CSV...")
    df = pd.read_csv(INPUT_CSV, sep=',', decimal=',')
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # Converte colunas para número
    for col in ['abertura', 'maxima', 'minima', 'fechamento', 'volume']:
        df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    df.rename(columns={
        'abertura': 'open', 'maxima': 'high', 'minima': 'low',
        'fechamento': 'close', 'volume': 'volume'
    }, inplace=True)
    return df[['open', 'high', 'low', 'close', 'volume']]

def test_threshold(df_15min, threshold):
    """Testa um threshold específico e retorna trades."""
    lookback = 20
    df = df_15min.copy()
    df['high_d'] = df['high'].rolling(lookback).max()
    df['low_d'] = df['low'].rolling(lookback).min()
    df['vol_ma'] = df['volume'].rolling(lookback).mean()
    df = df.dropna()
    
    trades = []
    position = 0
    entry = 0
    
    for i in range(len(df)):
        close = df.iloc[i]['close']
        high_d = df.iloc[i]['high_d']
        low_d = df.iloc[i]['low_d']
        vol_ratio = df.iloc[i]['volume'] / df.iloc[i]['vol_ma'] if df.iloc[i]['vol_ma'] > 0 else 0
        
        signal = 0
        if close > high_d and vol_ratio > threshold:
            signal = 1
        elif close < low_d and vol_ratio > threshold:
            signal = -1
        
        if position == 0 and signal != 0:
            position = signal
            entry = close
        elif position != 0 and signal == -position:
            exit_price = close
            if position == 1:
                raw = exit_price - entry
            else:
                raw = entry - exit_price
            trades.append(raw)
            position = 0
    
    if trades:
        expectancy = np.mean(trades)
        win_rate = np.sum(np.array(trades) > 0) / len(trades)
        return len(trades), expectancy, win_rate
    return 0, 0, 0

def main():
    df_1min = load_data()
    print(f"Dados 1min: {len(df_1min)} registros")
    
    # Agrega para 15min
    ohlc = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
    df_15min = df_1min.resample('15min').agg(ohlc).dropna()
    print(f"Dados 15min: {len(df_15min)} registros")
    
    print("\n" + "="*60)
    print("TESTANDO DIFERENTES THRESHOLDS DE VOLUME (15min)")
    print("="*60)
    
    thresholds = [1.0, 1.2, 1.5, 2.0, 3.0, 5.0, 10.0]
    
    for thresh in thresholds:
        trades_count, expectancy, win_rate = test_threshold(df_15min, thresh)
        if trades_count > 0:
            print(f"Threshold {thresh:4.1f}x | Trades: {trades_count:4d} | Expectancy: {expectancy:7.2f} pts | Win Rate: {win_rate*100:5.1f}%")
        else:
            print(f"Threshold {thresh:4.1f}x | Nenhum trade")
    
    # Teste SEM filtro de volume (apenas Donchian puro)
    print("\n" + "-"*60)
    print("TESTE APENAS DONCHIAN (sem filtro de volume)")
    trades_count, expectancy, win_rate = test_threshold(df_15min, 0)
    if trades_count > 0:
        print(f"Donchian puro      | Trades: {trades_count:4d} | Expectancy: {expectancy:7.2f} pts | Win Rate: {win_rate*100:5.1f}%")

if __name__ == "__main__":
    main()
