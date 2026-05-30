@"
import pandas as pd
import numpy as np
from pathlib import Path

SLIPPAGE_POINTS = 0.5
COMMISSION_REAIS = 0.30

def aggregate_to_5min(df: pd.DataFrame) -> pd.DataFrame:
    df = df.set_index('datetime')
    ohlc = df.resample('5min').agg({
        'abertura': 'first',
        'máxima': 'max',
        'mínima': 'min',
        'fechamento': 'last',
        'volume': 'sum'
    }).dropna().reset_index()
    return ohlc

def donchian_volume_strategy(df: pd.DataFrame, lookback: int = 20, vol_lookback: int = 20) -> pd.DataFrame:
    df = df.copy()
    df['max_high'] = df['máxima'].rolling(lookback).max()
    df['min_low'] = df['mínima'].rolling(lookback).min()
    df['volume_ma'] = df['volume'].rolling(vol_lookback).mean()
    buy_signal = (df['fechamento'] > df['max_high'].shift(1)) & (df['volume'] > df['volume_ma'].shift(1))
    sell_signal = (df['fechamento'] < df['min_low'].shift(1)) & (df['volume'] > df['volume_ma'].shift(1))
    df['sinal'] = 0
    df.loc[buy_signal, 'sinal'] = 1
    df.loc[sell_signal, 'sinal'] = -1
    df['posicao'] = df['sinal'].shift(1).fillna(0)
    return df

def backtest_with_costs(df: pd.DataFrame):
    df = donchian_volume_strategy(df)
    trades = []
    position = 0
    entry_price = 0
    entry_time = None
    side = None
    for idx, row in df.iterrows():
        new_pos = row['posicao']
        if new_pos != position:
            if position != 0:
                exit_price = row['fechamento']
                if side == 'long':
                    pnl_points = (exit_price - entry_price) - 2 * SLIPPAGE_POINTS
                else:
                    pnl_points = (entry_price - exit_price) - 2 * SLIPPAGE_POINTS
                pnl_reais = pnl_points * 10 - COMMISSION_REAIS
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': row['datetime'],
                    'pnl_points': pnl_points,
                    'pnl_reais': pnl_reais,
                    'side': side
                })
            if new_pos != 0:
                position = new_pos
                entry_price = row['fechamento']
                entry_time = row['datetime']
                side = 'long' if new_pos == 1 else 'short'
            else:
                position = 0
    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        return trades_df, 0.0, 0.0, 0.0, 0.0
    expectancy = trades_df['pnl_points'].mean()
    win_rate = (trades_df['pnl_points'] > 0).mean()
    total_trades = len(trades_df)
    equity = (1 + trades_df['pnl_points'] / 10000).cumprod()
    running_max = equity.cummax()
    max_dd = (running_max - equity).max() / running_max.max()
    return trades_df, expectancy, win_rate, total_trades, max_dd

def main():
    data_path = Path(r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_processado.parquet")
    df = pd.read_parquet(data_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    if 'maxima' in df.columns:
        df.rename(columns={'maxima': 'máxima', 'minima': 'mínima'}, inplace=True)
    df_5min = aggregate_to_5min(df)
    print(f"Dados 5min: {len(df_5min)} registros")
    split_idx = int(len(df_5min) * 0.8)
    test = df_5min.iloc[split_idx:].copy()
    print(f"Período de teste: {test['datetime'].min()} -> {test['datetime'].max()}")
    trades_df, expectancy, win_rate, total_trades, max_dd = backtest_with_costs(test)
    if trades_df.empty:
        print("Nenhum trade gerado.")
        return
    print("\n=== RESULTADO WDO 5min - Donchian+Volume (com custos) ===")
    print(f"Trades: {total_trades}")
    print(f"Expectancy líquida (pontos): {expectancy:.4f}")
    print(f"Win rate: {win_rate:.2%}")
    print(f"Max Drawdown (equity): {max_dd:.2%}")
    trades_df.to_csv("graficos/trades_wdo_5min.csv", index=False)
    print("Trades salvos em 'graficos/trades_wdo_5min.csv'")

if __name__ == "__main__":
    main()
"@ | Out-File -FilePath "run_5min_analysis.py" -Encoding utf8