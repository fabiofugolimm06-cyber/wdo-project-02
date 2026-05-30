import pandas as pd
import numpy as np
from pathlib import Path
import sys
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent))
from oos_engine import split_out_of_sample

def add_market_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # True Range e ATR
    df['prev_close'] = df['fechamento'].shift(1)
    df['tr'] = np.maximum(df['máxima'] - df['mínima'],
                  np.maximum(abs(df['máxima'] - df['prev_close']),
                             abs(df['mínima'] - df['prev_close'])))
    df['atr'] = df['tr'].rolling(20).mean()
    df['atr_ma'] = df['atr'].rolling(40).mean()
    df['vol_rel_atr'] = df['atr'] / df['atr_ma']
    
    # Range compression
    df['range'] = df['máxima'] - df['mínima']
    df['range_ma'] = df['range'].rolling(20).mean()
    df['range_compress'] = df['range'] / df['range_ma']
    
    # Volume relativo
    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['vol_rel'] = df['volume'] / df['volume_ma']
    
    # Distância da média (normalizada)
    df['mm20'] = df['fechamento'].rolling(20).mean()
    df['dist_mm'] = (df['fechamento'] - df['mm20']) / (df['atr'] + 1e-9)
    
    # Microestrutura: candle imbalance
    df['candle_imbalance'] = (df['fechamento'] - df['abertura']) / (df['range'] + 1e-9)
    
    # Eventos temporais
    hour = df['datetime'].dt.hour
    minute = df['datetime'].dt.minute
    df['is_open'] = (hour == 9) & (minute >= 0) & (hour < 10)
    df['is_mid'] = (hour >= 11) & (hour < 14)
    df['is_close'] = (hour >= 16) & (hour < 18)
    
    return df

def conditional_expectancy_with_costs(df: pd.DataFrame, condition_col: str, bins: int = 5, slippage_points: float = 0.5):
    """
    Calcula expectancy líquida de uma estratégia que opera sempre que a condição é verdadeira.
    Compra no fechamento, vende no próximo fechamento. Custos: slippage ida+volta (2 x slippage_points).
    """
    df = df.copy()
    df['ret_future'] = df['fechamento'].shift(-1) / df['fechamento'] - 1
    df['cond_bin'] = pd.cut(df[condition_col], bins=bins)
    results = []
    for name, group in df.groupby('cond_bin', observed=False):
        if len(group) < 10:
            continue
        # Simular trade: comprar e vender no próximo candle
        pnl_points = group['ret_future'] * group['fechamento'] - 2 * slippage_points
        expectancy = pnl_points.mean()
        win_rate = (pnl_points > 0).mean()
        results.append({'condition_range': str(name), 'trades': len(group), 
                        'expectancy_pts': expectancy, 'win_rate': win_rate})
    return pd.DataFrame(results)

def main():
    data_path = Path(r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_processado.parquet")
    df = pd.read_parquet(data_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    if 'maxima' in df.columns:
        df.rename(columns={'maxima': 'máxima', 'minima': 'mínima'}, inplace=True)
    
    df = add_market_features(df)
    split_date = df['datetime'].quantile(0.8)
    train, test = split_out_of_sample(df, split_date)
    
    print("=== ANÁLISE DE SUBESPAÇOS - EXPECTANCY CONDICIONAL (com custos) ===\n")
    
    # 1. Interação simples: volume alto + range comprimido
    test['high_vol'] = test['vol_rel'] > 1.5
    test['low_range'] = test['range_compress'] < 0.8
    test['signal'] = test['high_vol'] & test['low_range']
    
    test['ret_future'] = test['fechamento'].shift(-1) / test['fechamento'] - 1
    trades = test[test['signal']].copy()
    if len(trades) > 0:
        pnl_points = trades['ret_future'] * trades['fechamento'] - 1.0  # 2 x 0.5 slippage
        expectancy = pnl_points.mean()
        win_rate = (pnl_points > 0).mean()
        print(f"Condição: volume > 1.5x média E range < 0.8x média")
        print(f"Trades: {len(trades)}")
        print(f"Expectancy líquida (pts): {expectancy:.4f}")
        print(f"Win rate: {win_rate:.2%}\n")
    else:
        print("Nenhum trade para essa condição.\n")
    
    # 2. Análise sistemática por volume relativo
    print("--- Expectancy por volume relativo ---")
    vol_exp = conditional_expectancy_with_costs(test, 'vol_rel', bins=5)
    print(vol_exp.to_string(index=False), "\n")
    
    # 3. Por range compression
    print("--- Expectancy por range compression ---")
    range_exp = conditional_expectancy_with_costs(test, 'range_compress', bins=5)
    print(range_exp.to_string(index=False), "\n")
    
    # 4. Heatmap 2D: volume vs range
    test['vol_bin'] = pd.cut(test['vol_rel'], bins=5, labels=False)
    test['range_bin'] = pd.cut(test['range_compress'], bins=5, labels=False)
    matrix = test.groupby(['vol_bin', 'range_bin']).apply(
        lambda g: (g['ret_future'] * g['fechamento'] - 1.0).mean() if len(g) > 5 else np.nan
    ).unstack()
    
    plt.figure(figsize=(10,6))
    im = plt.imshow(matrix.values, aspect='auto', cmap='RdYlGn', vmin=-1, vmax=1)
    plt.colorbar(im, label='Expectancy líquida (pts)')
    plt.title('Expectancy líquida por Volume Relativo vs Range Compression')
    plt.xlabel('Range compression bin (0 = mais comprimido)')
    plt.ylabel('Volume relativo bin (0 = mais baixo)')
    plt.savefig('graficos/expectancy_heatmap.png', dpi=100)
    plt.close()
    print("Heatmap salvo em 'graficos/expectancy_heatmap.png'")
    
    # 5. Análise por eventos temporais
    print("--- Expectancy por período do dia (com custos) ---")
    for period, mask in [('Abertura (9-10)', test['is_open']),
                         ('Meio do dia (11-14)', test['is_mid']),
                         ('Fechamento (16-18)', test['is_close'])]:
        period_trades = test[mask].copy()
        if len(period_trades) > 0:
            pnl = period_trades['ret_future'] * period_trades['fechamento'] - 1.0
            print(f"{period}: trades={len(period_trades)}, expectancy={pnl.mean():.4f}, win_rate={(pnl>0).mean():.2%}")
        else:
            print(f"{period}: sem dados")

if __name__ == "__main__":
    main()