import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from oos_engine import split_out_of_sample
from regime_filter import add_regime_filter
from metrics_engine import calculate_metrics
from monte_carlo import monte_carlo_resample
from cost_model import adjust_trade_costs, SLIPPAGE_POINTS
from strategies import BollingerMeanReversion20

def simulate_trades_with_costs(df: pd.DataFrame, strategy, slippage_points: float = 0.5):
    """Simula trades considerando custos e slippage, retornando DataFrame de trades."""
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
                # Custo fixo por contrato
                cost_reais = 0.30
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
    return pd.DataFrame(trades)

def main():
    # Caminho dos dados
    data_path = r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_processado.parquet"
    df = pd.read_parquet(data_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    if 'maxima' in df.columns:
        df.rename(columns={'maxima': 'máxima', 'minima': 'mínima'}, inplace=True)
    
    # Separar OOS (20% final)
    split_date = df['datetime'].quantile(0.8)
    _, test = split_out_of_sample(df, split_date)
    
    strategy = BollingerMeanReversion20()
    
    # Simular com slippage padrão (0.5)
    trades = simulate_trades_with_costs(test, strategy, slippage_points=0.5)
    
    # Métricas
    print("=== BOLLINGER MEAN REVERSION - RELATÓRIO DE ROBUSTEZ ===\n")
    print(f"Período de teste: {test['datetime'].min()} -> {test['datetime'].max()}")
    print(f"Total de trades: {len(trades)}")
    print(f"Trades long: {(trades['side']=='long').sum()}")
    print(f"Trades short: {(trades['side']=='short').sum()}")
    
    if len(trades) > 0:
        print(f"\nExpectancy (pontos líquidos): {trades['pnl_points'].mean():.4f}")
        print(f"Expectancy (R$ por trade): {trades['pnl_reais'].mean():.2f}")
        print(f"Win rate: {(trades['pnl_points'] > 0).mean():.2%}")
        print(f"Profit factor: {abs(trades[trades['pnl_points']>0]['pnl_points'].sum() / trades[trades['pnl_points']<0]['pnl_points'].sum()):.2f}")
        print(f"Max drawdown (equity simulada): {((1 + trades['pnl_points']/10000).cumprod().cummax() - (1 + trades['pnl_points']/10000).cumprod()).max():.2%}")
        
        # Monte Carlo
        mc = monte_carlo_resample(trades, n_simulations=1000, capital_points=10000)
        print(f"\n=== MONTE CARLO (1000 simulações) ===")
        print(f"Median Max Drawdown: {mc['max_dd_median']:.2%}")
        print(f"95th percentile Max DD: {mc['max_dd_95pc']:.2%}")
        print(f"Median Expectancy (pontos): {mc['expectancy_median']:.4f}")
        print(f"5th percentile Expectancy: {mc['expectancy_5pc']:.4f}")
        
        # Sensibilidade ao slippage
        trades_slippage1 = simulate_trades_with_costs(test, strategy, slippage_points=1.0)
        print(f"\n=== SENSIBILIDADE AO SLIPPAGE ===")
        print(f"Com slippage 0.5 pt -> Expectancy: {trades['pnl_points'].mean():.4f}")
        print(f"Com slippage 1.0 pt -> Expectancy: {trades_slippage1['pnl_points'].mean():.4f}")
        
        # Gráfico equity curve
        equity = (1 + trades['pnl_points'] / 10000).cumprod()
        plt.figure(figsize=(12,5))
        plt.plot(trades['exit_time'], equity, linewidth=1)
        plt.title('Equity Curve - Bollinger Mean Reversion (OOS, custos inclusos)')
        plt.ylabel('Equity (base=1)')
        plt.grid(True)
        plt.savefig('graficos/bollinger_equity_curve.png', dpi=100)
        plt.close()
        
        # Histograma de PnL
        plt.figure(figsize=(10,4))
        plt.hist(trades['pnl_points'], bins=30, edgecolor='black', alpha=0.7)
        plt.title('Distribuição de PnL por Trade (pontos líquidos)')
        plt.xlabel('PnL (pontos)')
        plt.ylabel('Frequência')
        plt.grid(True)
        plt.savefig('graficos/bollinger_pnl_dist.png', dpi=100)
        plt.close()
        
        print("\nGráficos salvos em 'graficos/bollinger_equity_curve.png' e 'graficos/bollinger_pnl_dist.png'")
        
        # Salvar trades em CSV
        trades.to_csv('graficos/bollinger_trades.csv', index=False)
        print("Trades salvos em 'graficos/bollinger_trades.csv'")
    else:
        print("Nenhum trade gerado no período OOS.")

if __name__ == "__main__":
    main()