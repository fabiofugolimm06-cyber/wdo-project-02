import os
import yaml
import pandas as pd
import numpy as np
from datetime import datetime
from walkforward import walkforward_validation
from metrics import calculate_metrics
from report_generator import generate_report

# Configurações
CONFIG = {
    "data_path": os.path.join("C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02", "data", "wdo_1min.csv"),
    "lookback_atr": 20,
    "slippage_pts": 0.5,
    "risk_per_trade": 0.01,
    "initial_capital": 50000.0,
    "walkforward_windows": [
        {"train_start": "2024-01-01", "train_end": "2024-06-30",
         "test_start": "2024-07-01", "test_end": "2024-12-31"}
    ],
    "output_dir": os.path.join("C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02", "validation_reports")
}

def load_data(path):
    df = pd.read_csv(path, parse_dates=['datetime'])
    df.set_index('datetime', inplace=True)
    df.columns = [c.lower() for c in df.columns]
    return df

def compute_atr(df, period=20):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def compute_vwap(df):
    typical = (df['high'] + df['low'] + df['close']) / 3
    return (typical * df['volume']).cumsum() / df['volume'].cumsum()

def check_edge_01(df, idx, atr, avg_atr):
    if idx < 2 or pd.isna(atr[idx]) or pd.isna(avg_atr[idx]) or idx+1 >= len(df):
        return False
    if atr[idx] < 0.7 * avg_atr[idx] and df['close'].iloc[idx] != df['open'].iloc[idx]:
        close2 = df['close'].iloc[idx+1]
        high1 = df['high'].iloc[idx]
        low1 = df['low'].iloc[idx]
        vol2 = df['volume'].iloc[idx+1]
        avg_vol = df['volume'].rolling(20).mean().iloc[idx+1]
        if (close2 > high1 + 0.5 or close2 < low1 - 0.5) and vol2 > avg_vol:
            return True
    return False

def simulate_trade(entry_idx, direction, df, atr, capital, risk_per_trade):
    entry = df['close'].iloc[entry_idx+1]
    stop_pts = atr[entry_idx+1] + 0.5
    stop = entry - stop_pts if direction == 'long' else entry + stop_pts
    for i in range(entry_idx+2, len(df)):
        if direction == 'long' and df['low'].iloc[i] <= stop:
            exit_price = stop
            break
        elif direction == 'short' and df['high'].iloc[i] >= stop:
            exit_price = stop
            break
    else:
        exit_price = df['close'].iloc[-1]
    mult = 10.0
    pnl = (exit_price - entry) * mult if direction == 'long' else (entry - exit_price) * mult
    return pnl, capital + pnl

def run_validation(df, train_start, train_end, test_start, test_end):
    test = df.loc[test_start:test_end]
    atr = compute_atr(df, 20)
    avg_atr = atr.rolling(20).mean()
    trades = []
    capital = CONFIG['initial_capital']
    for idx in range(len(test)):
        global_idx = df.index.get_loc(test.index[idx])
        if global_idx < 20: continue
        if check_edge_01(df, global_idx, atr, avg_atr):
            direction = 'long' if df['close'].iloc[global_idx] > df['open'].iloc[global_idx] else 'short'
            pnl, capital = simulate_trade(global_idx, direction, df, atr, capital, CONFIG['risk_per_trade'])
            trades.append({'edge': 'ET-01', 'entry_time': test.index[idx], 'direction': direction, 'pnl': pnl})
    metrics = calculate_metrics(trades)
    return metrics, trades

def main():
    os.makedirs(CONFIG['output_dir'], exist_ok=True)
    df = load_data(CONFIG['data_path'])
    for w in CONFIG['walkforward_windows']:
        metrics, trades = run_validation(df, w['train_start'], w['train_end'], w['test_start'], w['test_end'])
        report_path = os.path.join(CONFIG['output_dir'], f"validation_{w['test_start']}_{w['test_end']}.yaml")
        generate_report(metrics, trades, w, report_path)
        print(f"Validação concluída para {w['test_start']} a {w['test_end']}")

if __name__ == "__main__":
    main()
