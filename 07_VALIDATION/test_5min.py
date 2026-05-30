import pandas as pd
import numpy as np
from pathlib import Path
import sys
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent))

from oos_engine import split_out_of_sample
from regime_filter import add_regime_filter
from cost_model import COMMISSION_PER_CONTRACT, FEES_B3_PER_CONTRACT
from strategies import BreakoutDonchianWithVolume
from strategy_base import StrategyBase

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

def backtest_with_costs_5min(df: pd.DataFrame, strategy: StrategyBase, slippage_points: float = 0.5) -> tuple:
    df = df.copy()
    df = strategy.generate_signals(df)
    df = add_regime_filter(df)
    
    trades = []
    position = 0
    entry_price = 0
    entry_time = None
    side = None
    
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
    
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
    if not trades_df.empty:
        equity = (1 + trades_df['pnl_points'] / 10000).cumprod()
        running_max = equity.cummax()
        max_dd = (running_max - equity).max() / running_max.max()
    else:
        max_dd = 0
    return trades_df, max_dd

def main():
    data_path = Path(r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_processado.parquet")
    df = pd.read_parquet(data_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    if 'maxima' in df.columns:
        df.rename(columns={'maxima': 'máxima', 'minima': 'mínima'}, inplace=True)
    
    # Agrega para 5min
    df_5min = aggregate_to_5min(df)
    print(f"Dados 5min: {len(df_5min)} registros")
    
    # Separa OOS (80/20)
    split_date = df_5min['datetime'].quantile(0.8)
    _, test = split_out_of_sample(df_5min, split_date)
    print(f"Período de teste (5min): {test['datetime'].min()} -> {test['datetime'].max()}")
    
    strategy = BreakoutDonchianWithVolume()
    trades_df, max_dd = backtest_with_costs_5min(test, strategy, slippage_points=0.5)
    
    if trades_df.empty:
        print("Nenhum trade gerado.")
        return
    
    expectancy = trades_df['pnl_points'].mean()
    win_rate = (trades_df['pnl_points'] > 0).mean()
    profit_factor = abs(trades_df[trades_df['pnl_points']>0]['pnl_points'].sum() / trades_df[trades_df['pnl_points']<0]['pnl_points'].sum()) if (trades_df['pnl_points']<0).any() else np.inf
    total_trades = len(trades_df)
    
    print("\n=== RESULTADO DONCHIAN+VOLUME EM 5 MINUTOS (com custos) ===")
    print(f"Trades: {total_trades}")
    print(f"Expectancy líquida (pontos): {expectancy:.4f}")
    print(f"Win rate: {win_rate:.2%}")
    print(f"Profit factor: {profit_factor:.2f}")
    print(f"Max Drawdown: {max_dd:.2%}")
    
    # Gráfico equity
    equity = (1 + trades_df['pnl_points'] / 10000).cumprod()
    plt.figure(figsize=(10,5))
    plt.plot(equity.values, linewidth=1)
    plt.title('Equity Curve - Donchian+Volume (5min) com custos')
    plt.xlabel('Trade #')
    plt.ylabel('Equity (base=1)')
    plt.grid()
    plt.savefig('graficos/equity_5min_donchian_volume.png', dpi=100)
    plt.close()
    print("Gráfico salvo em 'graficos/equity_5min_donchian_volume.png'")

if __name__ == "__main__":
    main()