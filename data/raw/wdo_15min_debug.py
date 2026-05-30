"""
wdo_15min_debug.py - Diagnóstico completo dos dados
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

def analyze_data(df_15min):
    """Analisa os dados para entender por que não há trades."""
    print("\n" + "="*60)
    print("ANÁLISE DOS DADOS - WDO 15min")
    print("="*60)
    
    # Estatísticas básicas
    print(f"\n📊 Estatísticas dos preços:")
    print(f"   Close min: {df_15min['close'].min():.2f}")
    print(f"   Close max: {df_15min['close'].max():.2f}")
    print(f"   Close médio: {df_15min['close'].mean():.2f}")
    
    print(f"\n📊 Estatísticas do volume:")
    print(f"   Volume min: {df_15min['volume'].min():.0f}")
    print(f"   Volume max: {df_15min['volume'].max():.0f}")
    print(f"   Volume médio: {df_15min['volume'].mean():.0f}")
    
    # Testa Donchian com diferentes lookbacks
    print(f"\n🔍 Testando Donchian com diferentes lookbacks (sem filtro volume):")
    
    for lookback in [5, 10, 20, 30, 50]:
        df = df_15min.copy()
        df['high_d'] = df['high'].rolling(lookback).max()
        df['low_d'] = df['low'].rolling(lookback).min()
        df = df.dropna()
        
        # Conta sinais
        buy_signals = (df['close'] > df['high_d'].shift(1)).sum()
        sell_signals = (df['close'] < df['low_d'].shift(1)).sum()
        
        print(f"   Lookback {lookback:2d}: Buy={buy_signals:4d}, Sell={sell_signals:4d}, Total={buy_signals+sell_signals:4d}")
    
    # Mostra exemplo de uma barra típica
    print(f"\n📝 Exemplo de dados (primeiras 5 barras válidas):")
    print(df_15min.head(10))
    
    # Verifica se há variação nos preços
    price_change = df_15min['close'].pct_change().abs()
    print(f"\n📈 Volatilidade média (retorno absoluto): {price_change.mean()*100:.4f}%")
    
    # Testa Donchian puro com lookback 20 e mostra primeiros sinais
    print(f"\n🎯 Teste prático Donchian (lookback=20):")
    df = df_15min.copy()
    df['high_d'] = df['high'].rolling(20).max()
    df['low_d'] = df['low'].rolling(20).min()
    df = df.dropna()
    
    df['signal'] = 0
    df.loc[df['close'] > df['high_d'].shift(1), 'signal'] = 1
    df.loc[df['close'] < df['low_d'].shift(1), 'signal'] = -1
    
    signal_count = (df['signal'] != 0).sum()
    print(f"   Total de sinais: {signal_count}")
    
    if signal_count > 0:
        print(f"\n   Primeiros 10 sinais encontrados:")
        signals_df = df[df['signal'] != 0][['close', 'high_d', 'low_d', 'signal']].head(10)
        print(signals_df)
    else:
        print("   ⚠️ NENHUM sinal encontrado! Verificando condição...")
        
        # Verifica condição manualmente
        last_row = df.iloc[0]
        print(f"\n   Verificando primeira barra:")
        print(f"      Close: {last_row['close']:.2f}")
        print(f"      High_D (shift 1): {last_row['high_d']:.2f}")
        print(f"      Low_D (shift 1): {last_row['low_d']:.2f}")
        print(f"      Close > High_D? {last_row['close'] > last_row['high_d']}")
        print(f"      Close < Low_D? {last_row['close'] < last_row['low_d']}")

def main():
    df_1min = load_data()
    print(f"Dados 1min: {len(df_1min)} registros")
    
    # Agrega para 15min
    ohlc = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
    df_15min = df_1min.resample('15min').agg(ohlc).dropna()
    print(f"Dados 15min: {len(df_15min)} registros")
    
    analyze_data(df_15min)

if __name__ == "__main__":
    main()
