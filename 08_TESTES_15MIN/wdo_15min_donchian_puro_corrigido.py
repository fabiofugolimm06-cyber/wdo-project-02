"""
wdo_15min_donchian_puro_corrigido.py - Donchian puro com salvamento de trades
"""

import pandas as pd
import numpy as np
from pathlib import Path

INPUT_CSV = r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_OHLC.csv"

SLIPPAGE_POINTS = 0.5
COMMISSION_BRL = 0.30
POINT_VALUE = 10.0

LOOKBACK = 20
TRAIN_BARS = 3000
TEST_BARS = 1000

def load_data():
    print("📂 Lendo CSV...")
    df = pd.read_csv(INPUT_CSV, sep=',', decimal=',')
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    for col in ['abertura', 'maxima', 'minima', 'fechamento', 'volume']:
        df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    df.rename(columns={
        'abertura': 'open', 'maxima': 'high', 'minima': 'low',
        'fechamento': 'close', 'volume': 'volume'
    }, inplace=True)
    return df[['open', 'high', 'low', 'close', 'volume']]

def aggregate_to_15min(df_1min):
    print("🕒 Agregando para 15min...")
    ohlc = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
    df_15 = df_1min.resample('15min').agg(ohlc).dropna()
    print(f"   Barras de 15min: {len(df_15)}")
    return df_15

def run_walk_forward_donchian(df):
    print("🚀 Executando walk-forward Donchian puro...\n")
    all_trades = []
    trades_list = []  # para salvar detalhes
    
    n = len(df)
    n_splits = 0
    
    for start in range(0, n - TRAIN_BARS - TEST_BARS, TEST_BARS):
        train_end = start + TRAIN_BARS
        test_end = train_end + TEST_BARS
        
        df_test = df.iloc[train_end:test_end].copy()
        
        df_test['high_d'] = df['high'].rolling(LOOKBACK).max().shift(1)
        df_test['low_d'] = df['low'].rolling(LOOKBACK).min().shift(1)
        df_test = df_test.dropna()
        
        position = 0
        entry_price = 0
        entry_time = None
        trades_in_split = 0
        
        for i in range(len(df_test)):
            close = df_test.iloc[i]['close']
            high_d = df_test.iloc[i]['high_d']
            low_d = df_test.iloc[i]['low_d']
            current_time = df_test.index[i]
            
            signal = 0
            if close > high_d:
                signal = 1
            elif close < low_d:
                signal = -1
            
            if position == 0 and signal != 0:
                position = signal
                entry_price = close
                entry_time = current_time
                trades_in_split += 1
            elif position != 0 and signal == -position:
                exit_price = close
                exit_time = current_time
                
                if position == 1:
                    raw = exit_price - entry_price
                else:
                    raw = entry_price - exit_price
                
                cost_pts = SLIPPAGE_POINTS + (COMMISSION_BRL / POINT_VALUE)
                net = raw - cost_pts
                all_trades.append(net)
                
                # Salva detalhes do trade
                trades_list.append({
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'direction': position,
                    'raw_return': raw,
                    'net_return': net
                })
                position = 0
        
        if position != 0:
            exit_price = df_test.iloc[-1]['close']
            exit_time = df_test.index[-1]
            if position == 1:
                raw = exit_price - entry_price
            else:
                raw = entry_price - exit_price
            cost_pts = SLIPPAGE_POINTS + (COMMISSION_BRL / POINT_VALUE)
            net = raw - cost_pts
            all_trades.append(net)
            
            trades_list.append({
                'entry_time': entry_time,
                'exit_time': exit_time,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'direction': position,
                'raw_return': raw,
                'net_return': net
            })
        
        if trades_in_split > 0:
            n_splits += 1
            print(f"   Split {n_splits}: {trades_in_split} trades")
    
    return all_trades, trades_list

def main():
    df_1min = load_data()
    df_15min = aggregate_to_15min(df_1min)
    
    trades_net, trades_list = run_walk_forward_donchian(df_15min)
    
    # Salva trades em CSV
    if trades_list:
        trades_df = pd.DataFrame(trades_list)
        trades_df.to_csv("trades_15min.csv", index=False)
        print(f"\n💾 Trades salvos em trades_15min.csv")
    
    print("\n" + "="*50)
    print("📈 RESULTADO WDO 15min - DONCHIAN PURO (com custos)")
    print("="*50)
    
    if trades_net:
        expectancy = np.mean(trades_net)
        win_rate = np.sum(np.array(trades_net) > 0) / len(trades_net)
        
        print(f"   Total de trades: {len(trades_net)}")
        print(f"   Expectancy líquida: {expectancy:.2f} pontos")
        print(f"   Win rate: {win_rate*100:.1f}%")
        
        if expectancy > 0:
            print("\n   ✅ Estratégia lucrativa após custos!")
        else:
            print("\n   ❌ Expectancy negativa (não viável com custos reais)")
    else:
        print("   ❌ Nenhum trade gerado")

if __name__ == "__main__":
    main()
