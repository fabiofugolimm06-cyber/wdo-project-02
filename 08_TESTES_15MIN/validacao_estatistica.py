"""
validacao_estatistica.py
Validacao estatistica rigorosa da hipotese de edge bruto no WDO 15min.
"""

import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
from pathlib import Path

# ================= CONFIGURACOES =================
INPUT_CSV = r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_OHLC.csv"
TRADES_CSV = "trades_15min.csv"

SLIPPAGE_POINTS = 0.5
COMMISSION_BRL = 0.30
POINT_VALUE = 10.0
COST_PTS = SLIPPAGE_POINTS + (COMMISSION_BRL / POINT_VALUE)

N_BOOTSTRAP = 10000
N_PERMUTATIONS = 10000
CONFIDENCE_LEVEL = 0.95
# =================================================

def load_trades():
    try:
        trades_df = pd.read_csv(TRADES_CSV)
        print(f"Carregados {len(trades_df)} trades do arquivo {TRADES_CSV}")
        
        raw_returns = []
        for idx, row in trades_df.iterrows():
            direction = row['direction']
            entry = row['entry_price']
            exit_ = row['exit_price']
            
            if direction == 1:
                ret = exit_ - entry
            else:
                ret = entry - exit_
            raw_returns.append(ret)
        
        raw_returns = np.array(raw_returns)
        net_returns = raw_returns - COST_PTS
        
        return raw_returns, net_returns, trades_df
    
    except FileNotFoundError:
        print(f"Arquivo {TRADES_CSV} nao encontrado.")
        print("Execute wdo_15min_donchian_puro.py primeiro para gerar os trades.")
        return None, None, None

def bootstrap_confidence_interval(data, n_bootstrap=N_BOOTSTRAP, alpha=0.05):
    print("\n" + "="*60)
    print("1. BOOTSTRAP CONFIDENCE INTERVAL")
    print("="*60)
    
    means = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(data, size=len(data), replace=True)
        means.append(np.mean(sample))
    
    means = np.array(means)
    lower = np.percentile(means, 100 * alpha/2)
    upper = np.percentile(means, 100 * (1 - alpha/2))
    
    print(f"   Media observada: {np.mean(data):.4f} pontos")
    print(f"   IC {int((1-alpha)*100)}%: [{lower:.4f}, {upper:.4f}]")
    print(f"   Desvio padrao bootstrap: {np.std(means):.4f}")
    
    contains_zero = (lower <= 0 <= upper)
    print(f"   Contem zero? {'SIM (nao significativo)' if contains_zero else 'NAO (significativo)'}")
    
    return means, lower, upper, contains_zero

def t_test(data):
    print("\n" + "="*60)
    print("2. TESTE T (media vs zero)")
    print("="*60)
    
    t_stat, p_value = stats.ttest_1samp(data, 0)
    
    print(f"   t-statistic: {t_stat:.4f}")
    print(f"   p-value: {p_value:.6f}")
    print(f"   Graus de liberdade: {len(data)-1}")
    
    significant = p_value < 0.05
    print(f"   Significativo (p<0.05)? {'SIM' if significant else 'NAO'}")
    
    return t_stat, p_value, significant

def permutation_test(data, n_permutations=N_PERMUTATIONS):
    print("\n" + "="*60)
    print("3. PERMUTATION TEST (embaralhamento de sinais)")
    print("="*60)
    
    observed_mean = np.mean(data)
    
    perm_means = []
    abs_data = np.abs(data)
    
    for _ in range(n_permutations):
        signs = np.random.choice([-1, 1], size=len(data))
        perm_data = abs_data * signs
        perm_means.append(np.mean(perm_data))
    
    perm_means = np.array(perm_means)
    p_value = np.mean(np.abs(perm_means) >= np.abs(observed_mean))
    
    print(f"   Media observada: {observed_mean:.4f}")
    print(f"   Media das permutacoes: {np.mean(perm_means):.4f}")
    print(f"   p-value: {p_value:.6f}")
    
    significant = p_value < 0.05
    print(f"   Significativo (p<0.05)? {'SIM' if significant else 'NAO'}")
    
    return perm_means, p_value, significant

def random_entry_comparison(df_15min, trades_df):
    print("\n" + "="*60)
    print("4. RANDOM ENTRIES (mesma distribuicao de tempo)")
    print("="*60)
    
    n_trades = len(trades_df)
    n_bars = len(df_15min)
    
    random_returns = []
    for _ in range(1000):
        random_indices = np.random.choice(n_bars - 20, size=n_trades, replace=False)
        random_returns_this = []
        
        for idx in random_indices:
            if idx + 2 < n_bars:
                ret = df_15min.iloc[idx + 2]['close'] - df_15min.iloc[idx]['close']
                random_returns_this.append(ret)
        
        if random_returns_this:
            random_returns.append(np.mean(random_returns_this))
    
    random_returns = np.array(random_returns)
    observed_mean = np.mean([(t['exit_price'] - t['entry_price']) * (1 if t['direction']==1 else -1) 
                              for _, t in trades_df.iterrows()])
    
    p_value = np.mean(random_returns >= observed_mean)
    
    print(f"   Media observada (estrategia): {observed_mean:.4f}")
    print(f"   Media entradas aleatorias: {np.mean(random_returns):.4f}")
    print(f"   p-value: {p_value:.4f}")
    
    better_than_random = p_value < 0.05
    print(f"   Melhor que aleatorio? {'SIM' if better_than_random else 'NAO'}")
    
    return random_returns, p_value, better_than_random

def stability_across_folds(trades_df):
    print("\n" + "="*60)
    print("5. STABILITY ACROSS WALK-FORWARD FOLDS")
    print("="*60)
    
    n_folds = 3
    fold_size = len(trades_df) // n_folds
    
    fold_means = []
    for i in range(n_folds):
        start = i * fold_size
        end = (i+1) * fold_size if i < n_folds-1 else len(trades_df)
        fold_trades = trades_df.iloc[start:end]
        
        fold_returns = []
        for _, row in fold_trades.iterrows():
            direction = row['direction']
            if direction == 1:
                ret = row['exit_price'] - row['entry_price']
            else:
                ret = row['entry_price'] - row['exit_price']
            fold_returns.append(ret)
        
        fold_mean = np.mean(fold_returns)
        fold_means.append(fold_mean)
        print(f"   Fold {i+1}: {len(fold_returns)} trades, mean = {fold_mean:.4f}")
    
    all_same_sign = all(m > 0 for m in fold_means) or all(m < 0 for m in fold_means)
    
    print(f"\n   Todos folds com mesmo sinal? {'SIM' if all_same_sign else 'NAO'}")
    
    std_across_folds = np.std(fold_means)
    print(f"   Desvio padrao entre folds: {std_across_folds:.4f}")
    print(f"   Coeficiente de variacao: {std_across_folds/abs(np.mean(fold_means)):.2f}")
    
    return fold_means, all_same_sign

def plot_bootstrap_distribution(bootstrap_means, observed_mean):
    plt.figure(figsize=(10, 6))
    plt.hist(bootstrap_means, bins=50, alpha=0.7, edgecolor='black', color='steelblue')
    plt.axvline(observed_mean, color='red', linewidth=2, label=f'Media observada: {observed_mean:.4f}')
    plt.axvline(0, color='green', linestyle='--', linewidth=1.5, label='Zero')
    plt.xlabel('Expectancy bruta (pontos)')
    plt.ylabel('Frequencia')
    plt.title('Distribuicao Bootstrap da Expectancy Bruta')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('bootstrap_distribution.png', dpi=150)
    print("\nGrafico salvo: bootstrap_distribution.png")

def main():
    print("="*60)
    print("VALIDACAO ESTATISTICA DE EDGE BRUTO - WDO 15min")
    print("="*60)
    
    raw_returns, net_returns, trades_df = load_trades()
    
    if raw_returns is None or len(raw_returns) == 0:
        print("Nao foi possivel carregar os trades. Execute o backtest primeiro.")
        return
    
    print(f"\nEstatisticas basicas dos {len(raw_returns)} trades:")
    print(f"   Expectancy bruta: {np.mean(raw_returns):.4f} pontos")
    print(f"   Expectancy liquida: {np.mean(net_returns):.4f} pontos")
    print(f"   Win rate bruto: {(np.array(raw_returns) > 0).mean():.1%}")
    
    bootstrap_means, lower, upper, contains_zero = bootstrap_confidence_interval(raw_returns)
    t_stat, p_value_t, significant_t = t_test(raw_returns)
    perm_means, p_value_perm, significant_perm = permutation_test(raw_returns)
    
    try:
        df_1min = pd.read_csv(INPUT_CSV, sep=',', decimal=',')
        df_1min['datetime'] = pd.to_datetime(df_1min['datetime'])
        for col in ['abertura', 'maxima', 'minima', 'fechamento', 'volume']:
            df_1min[col] = df_1min[col].astype(str).str.replace(',', '.').astype(float)
        df_1min.set_index('datetime', inplace=True)
        ohlc = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
        df_15min = df_1min.resample('15min').agg(ohlc).dropna()
        
        random_returns, p_value_rand, better_than_random = random_entry_comparison(df_15min, trades_df)
    except Exception as e:
        print(f"\nNao foi possivel executar teste de aleatorio: {e}")
        better_than_random = None
    
    fold_means, all_same_sign = stability_across_folds(trades_df)
    
    print("\n" + "="*60)
    print("CONCLUSAO FINAL")
    print("="*60)
    
    criteria = []
    criteria.append(("Bootstrap (IC nao contem zero)", not contains_zero))
    criteria.append(("Teste t (p < 0.05)", significant_t))
    criteria.append(("Permutation test (p < 0.05)", significant_perm))
    if better_than_random is not None:
        criteria.append(("Melhor que aleatorio (p < 0.05)", better_than_random))
    criteria.append(("Estabilidade (mesmo sinal entre folds)", all_same_sign))
    
    for name, result in criteria:
        print(f"   {name}: {'OK' if result else 'FALHA'}")
    
    n_passed = sum(result for _, result in criteria)
    n_total = len(criteria)
    
    print(f"\n   Criterios atendidos: {n_passed}/{n_total}")
    
    if n_passed >= 3:
        print("\nCONCLUSAO: A expectativa bruta e estatisticamente DIFERENTE DE ZERO.")
        print("   Existe evidencia de edge bruto no WDO 15min.")
    else:
        print("\nCONCLUSAO: A expectativa bruta NAO e estatisticamente diferente de zero.")
        print("   O desempenho observado e consistente com RUIDO.")
    
    plot_bootstrap_distribution(bootstrap_means, np.mean(raw_returns))
    
    print("\nResultados salvos:")
    print("   - bootstrap_distribution.png")

if __name__ == "__main__":
    main()
