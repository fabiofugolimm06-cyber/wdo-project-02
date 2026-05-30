"""
wdo_15min_correcao.py - VERSÃO COM CONVERSÃO DE TIPOS
Testa estratégias no WDO 15min com custos reais.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ================= CONFIGURAÇÕES =================
INPUT_CSV = r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_OHLC.csv"

SEP = ','
DECIMAL = ','
DATE_COL = 'datetime'

# Nomes das colunas em português
OPEN_COL = 'abertura'
HIGH_COL = 'maxima'
LOW_COL = 'minima'
CLOSE_COL = 'fechamento'
VOLUME_COL = 'volume'

# Custos
SLIPPAGE_POINTS = 0.5
COMMISSION_BRL = 0.30
POINT_VALUE = 10.0

# Walk-forward
TRAIN_BARS = 1800
TEST_BARS = 600

# Parâmetros
DONCHIAN_LOOKBACK = 20
VOLUME_THRESHOLD = 1.5
# =================================================

def load_data():
    """Carrega CSV com colunas em português e converte para números."""
    print("📂 Lendo CSV...")
    df = pd.read_csv(INPUT_CSV, sep=SEP, decimal=DECIMAL)
    
    # Converte datetime
    if DATE_COL in df.columns:
        df['datetime'] = pd.to_datetime(df[DATE_COL])
    
    # Converte colunas numéricas (substitui vírgula por ponto se necessário)
    for col in [OPEN_COL, HIGH_COL, LOW_COL, CLOSE_COL, VOLUME_COL]:
        if col in df.columns:
            # Se for string, substitui vírgula por ponto e converte
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    
    # Renomeia colunas
    df.rename(columns={
        OPEN_COL: 'open',
        HIGH_COL: 'high',
        LOW_COL: 'low',
        CLOSE_COL: 'close',
        VOLUME_COL: 'volume'
    }, inplace=True)
    
    df = df[['open', 'high', 'low', 'close', 'volume']]
    print(f"   Registros carregados: {len(df)}")
    print(f"   Tipos: open={df['open'].dtype}, volume={df['volume'].dtype}")
    return df

def aggregate_to_15min(df_1min):
    """Agrega dados de 1 minuto para 15 minutos."""
    print("🕒 Agregando para 15min...")
    
    # Garante que os dados são numéricos
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df_1min[col] = pd.to_numeric(df_1min[col], errors='coerce')
    
    ohlc = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    df_15 = df_1min.resample('15min').agg(ohlc).dropna()
    print(f"   Barras de 15min: {len(df_15)}")
    return df_15

def add_indicators(df):
    """Calcula indicadores Donchian + volume."""
    print("📊 Calculando indicadores...")
    df = df.copy()
    df['high_donchian'] = df['high'].rolling(DONCHIAN_LOOKBACK).max()
    df['low_donchian'] = df['low'].rolling(DONCHIAN_LOOKBACK).min()
    df['volume_ma'] = df['volume'].rolling(DONCHIAN_LOOKBACK).mean()
    return df

def run_walk_forward(df):
    """Executa walk-forward com estratégia Donchian+Volume."""
    print("🚀 Executando walk-forward com custos reais...\n")
    all_trades = []
    
    n = len(df)
    for start in range(0, n - TRAIN_BARS - TEST_BARS, TEST_BARS):
        train_end = start + TRAIN_BARS
        test_end = train_end + TEST_BARS
        
        df_test = df.iloc[train_end:test_end].copy()
        
        position = 0
        entry_price = 0
        
        for i in range(len(df_test)):
            idx = df_test.index[i]
            close = df_test.loc[idx, 'close']
            high_d = df_test.loc[idx, 'high_donchian']
            low_d = df_test.loc[idx, 'low_donchian']
            vol = df_test.loc[idx, 'volume']
            vol_ma = df_test.loc[idx, 'volume_ma']
            
            if pd.isna(high_d) or pd.isna(low_d) or pd.isna(vol_ma) or vol_ma == 0:
                continue
            
            # Sinal Donchian + volume
            signal = 0
            if close > high_d and vol / vol_ma > VOLUME_THRESHOLD:
                signal = 1
            elif close < low_d and vol / vol_ma > VOLUME_THRESHOLD:
                signal = -1
            
            if position == 0 and signal != 0:
                position = signal
                entry_price = close
            elif position != 0 and signal == -position:
                exit_price = close
                all_trades.append((entry_price, exit_price, position))
                position = 0
        
        if position != 0:
            exit_price = df_test.iloc[-1]['close']
            all_trades.append((entry_price, exit_price, position))
    
    return all_trades

def calculate_metrics(trades):
    """Calcula expectancy e win rate com custos."""
    if not trades:
        return None
    
    net_points = []
    for entry, exit_, direction in trades:
        if direction == 1:
            raw = exit_ - entry
        else:
            raw = entry - exit_
        
        cost_pts = SLIPPAGE_POINTS + (COMMISSION_BRL / POINT_VALUE)
        net = raw - cost_pts
        net_points.append(net)
    
    expectancy = np.mean(net_points)
    win_rate = np.sum(np.array(net_points) > 0) / len(net_points)
    
    return {
        'expectancy_pts': expectancy,
        'win_rate': win_rate,
        'total_trades': len(net_points)
    }

def main():
    try:
        df_1min = load_data()
        df_15min = aggregate_to_15min(df_1min)
        df_15min = add_indicators(df_15min)
        
        # Remove linhas com NaN nos indicadores
        df_15min = df_15min.dropna()
        print(f"   Dados após remover NaN: {len(df_15min)} barras")
        
        trades = run_walk_forward(df_15min)
        metrics = calculate_metrics(trades)
        
        print("\n" + "="*50)
        print("📈 RESULTADO WDO 15min - Donchian+Volume (com custos)")
        print("="*50)
        if metrics:
            print(f"   Expectancy líquida: {metrics['expectancy_pts']:.2f} pontos")
            print(f"   Win rate: {metrics['win_rate']*100:.1f}%")
            print(f"   Total de trades: {metrics['total_trades']}")
            
            if metrics['expectancy_pts'] > 0:
                print("\n   ✅ Estratégia lucrativa após custos!")
            else:
                print("\n   ❌ Expectancy negativa (não viável com custos reais)")
        else:
            print("   ❌ Nenhum trade gerado")
        
        if trades:
            trades_df = pd.DataFrame(trades, columns=['entry_price', 'exit_price', 'direction'])
            trades_df.to_csv("trades_15min.csv", index=False)
            print(f"\n   Trades salvos em: {Path('trades_15min.csv').absolute()}")
    
    except FileNotFoundError:
        print(f"❌ Arquivo não encontrado: {INPUT_CSV}")
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
