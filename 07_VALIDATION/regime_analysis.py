import pandas as pd
import numpy as np
from pathlib import Path
import sys
import matplotlib.pyplot as plt
from ta.trend import ADXIndicator

sys.path.insert(0, str(Path(__file__).parent.parent))

from oos_engine import split_out_of_sample
from cost_model import COMMISSION_PER_CONTRACT, FEES_B3_PER_CONTRACT

def detect_regime(df: pd.DataFrame, adx_period: int = 14, atr_period: int = 20, atr_threshold: float = 1.5):
    df = df.copy()
    # ADX real
    adx_ind = ADXIndicator(high=df['máxima'], low=df['mínima'], close=df['fechamento'], window=adx_period)
    df['adx'] = adx_ind.adx()
    
    # True Range e ATR
    df['prev_close'] = df['fechamento'].shift(1)
    df['tr'] = np.maximum(df['máxima'] - df['mínima'],
                  np.maximum(abs(df['máxima'] - df['prev_close']),
                             abs(df['mínima'] - df['prev_close'])))
    df['atr'] = df['tr'].rolling(atr_period).mean()
    df['atr_ma'] = df['atr'].rolling(atr_period * 2).mean()
    df['vol_regime'] = np.where(df['atr'] > atr_threshold * df['atr_ma'], 'high', 'normal')
    
    # Classificação de regime
    df['regime'] = 'transition'
    df.loc[df['adx'] > 25, 'regime'] = 'trend'
    df.loc[df['adx'] < 20, 'regime'] = 'range'
    
    return df

def regime_based_strategy(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    fast = 9
    slow = 21
    bb_window = 20
    bb_std = 2
    
    df['MM_fast'] = df['fechamento'].rolling(fast).mean()
    df['MM_slow'] = df['fechamento'].rolling(slow).mean()
    df['bb_mid'] = df['fechamento'].rolling(bb_window).mean()
    df['bb_std'] = df['fechamento'].rolling(bb_window).std()
    df['bb_upper'] = df['bb_mid'] + bb_std * bb_std
    df['bb_lower'] = df['bb_mid'] - bb_std * bb_std
    
    df['sinal'] = 0
    
    # Regime de tendência: seguir MM9/MM21
    trend_mask = df['regime'] == 'trend'
    df.loc[trend_mask & (df['MM_fast'] > df['MM_slow']), 'sinal'] = 1
    df.loc[trend_mask & (df['MM_fast'] < df['MM_slow']), 'sinal'] = -1
    
    # Regime de range: reversão à média com Bollinger
    range_mask = df['regime'] == 'range'
    df.loc[range_mask & (df['fechamento'] < df['bb_lower']), 'sinal'] = 1
    df.loc[range_mask & (df['fechamento'] > df['bb_upper']), 'sinal'] = -1
    
    # Regime de transição: neutro
    
    # Filtro de volatilidade: não operar se vol_regime == 'high'
    df['sinal'] = df['sinal'].where(df['vol_regime'] == 'normal', 0)
    
    df['posicao'] = df['sinal'].shift(1).fillna(0)
    return df

def backtest_with_costs(df: pd.DataFrame, slippage_points: float = 0.5):
    trades = []
    position = 0
    entry_price = 0
    entry_time = None
    side = None
    regime_at_entry = None
    
    for i, row in df.iterrows():
        new_pos = row['posicao']
        if new_pos != position:
            if position != 0:
                exit_price = row['fechamento']
                if side == 'long':
                    pnl_points = (exit_price - entry_price) - 2 * slippage_points
                else:
                    pnl_points = (entry_price - exit_price) - 2 * slippage_points
                cost_reais = COMMISSION_PER_CONTRACT + FEES_B3_PER_CONTRACT
                pnl_reais = pnl_points * 10 - cost_reais
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': row['datetime'],
                    'regime': regime_at_entry,
                    'pnl_points': pnl_points,
                    'pnl_reais': pnl_reais,
                    'side': side
                })
            if new_pos != 0:
                position = new_pos
                entry_price = row['fechamento']
                entry_time = row['datetime']
                side = 'long' if new_pos == 1 else 'short'
                regime_at_entry = row['regime']
            else:
                position = 0
    return pd.DataFrame(trades) if trades else pd.DataFrame()

def main():
    data_path = Path(r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_processado.parquet")
    df = pd.read_parquet(data_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    if 'maxima' in df.columns:
        df.rename(columns={'maxima': 'máxima', 'minima': 'mínima'}, inplace=True)
    
    df = detect_regime(df)
    
    split_date = df['datetime'].quantile(0.8)
    _, test = split_out_of_sample(df, split_date)
    print(f"Período de teste: {test['datetime'].min()} -> {test['datetime'].max()}")
    
    test = regime_based_strategy(test)
    trades_df = backtest_with_costs(test, slippage_points=0.5)
    
    if trades_df.empty:
        print("Nenhum trade gerado.")
        return
    
    regime_stats = trades_df.groupby('regime').agg(
        trades=('pnl_points', 'count'),
        expectancy_points=('pnl_points', 'mean'),
        win_rate=('pnl_points', lambda x: (x > 0).mean()),
        total_pnl=('pnl_points', 'sum')
    ).reset_index()
    regime_stats['expectancy_reais'] = regime_stats['expectancy_points'] * 10 - 0.30
    
    print("\n=== PERFORMANCE POR REGIME (com custos) ===")
    print(regime_stats.to_string(index=False))
    
    global_exp = trades_df['pnl_points'].mean()
    global_win = (trades_df['pnl_points'] > 0).mean()
    print(f"\nGlobal - Expectancy: {global_exp:.4f} pts | Win rate: {global_win:.2%}")
    
    equity = (1 + trades_df['pnl_points'] / 10000).cumprod()
    plt.figure(figsize=(10,5))
    plt.plot(equity.values, linewidth=1)
    plt.title('Equity Curve - Regime Switching (custos inclusos)')
    plt.xlabel('Trade #')
    plt.ylabel('Equity (base=1)')
    plt.grid()
    plt.savefig('graficos/equity_regime_switching.png', dpi=100)
    plt.close()
    print("Gráfico salvo em 'graficos/equity_regime_switching.png'")
    trades_df.to_csv('graficos/trades_regime_switching.csv', index=False)
    regime_stats.to_csv('graficos/regime_performance.csv', index=False)

if __name__ == "__main__":
    main()