import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from oos_engine import split_out_of_sample

def add_volume_features(df: pd.DataFrame, vol_lookback: int = 50) -> pd.DataFrame:
    df = df.copy()
    df['volume_ma'] = df['volume'].rolling(vol_lookback).mean()
    df['volume_rel'] = df['volume'] / df['volume_ma']
    return df

def extract_extreme_events(df: pd.DataFrame, threshold: float = 10.0, lookback: int = 20, forward: int = 20):
    """
    Para cada evento onde volume_rel > threshold, coleta retornos de uma janela ao redor.
    """
    events = []
    # Obter os índices (rótulos) onde a condição ocorre
    event_idx = df[df['volume_rel'] > threshold].index
    for idx in event_idx:
        pos = df.index.get_loc(idx)  # posição inteira
        start = max(0, pos - lookback)
        end = min(len(df)-1, pos + forward)
        if end - start + 1 < lookback + forward + 1:
            continue
        window_df = df.iloc[start:end+1].copy()
        # Retorno acumulado a partir do evento (candle do evento incluso)
        base_price = window_df.iloc[lookback]['fechamento']
        window_df['ret_acum'] = (window_df['fechamento'] / base_price - 1) * 100
        future_ret = (window_df.iloc[-1]['fechamento'] / base_price - 1) * 100
        events.append({
            'event_time': df.loc[idx, 'datetime'],
            'volume_rel': df.loc[idx, 'volume_rel'],
            'future_ret_pct': future_ret,
            'window_returns': window_df['ret_acum'].tolist(),
            'window_prices': window_df['fechamento'].tolist(),
            'window_dates': window_df['datetime'].tolist()
        })
    return pd.DataFrame(events)

def time_split_stability(events_df: pd.DataFrame, n_splits: int = 3):
    if events_df.empty:
        return pd.DataFrame()
    events_df = events_df.sort_values('event_time').reset_index(drop=True)
    splits = np.array_split(events_df, n_splits)
    results = []
    for i, split_df in enumerate(splits):
        expectancy = split_df['future_ret_pct'].mean()
        win_rate = (split_df['future_ret_pct'] > 0).mean()
        results.append({
            'split': i+1,
            'n_events': len(split_df),
            'expectancy_pct': expectancy,
            'win_rate': win_rate
        })
    return pd.DataFrame(results)

def bootstrap_extreme_trades(returns_series, n_bootstrap=10000):
    if len(returns_series) == 0:
        return np.array([])
    n = len(returns_series)
    boot_means = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(returns_series, size=n, replace=True)
        boot_means.append(np.mean(sample))
    return np.array(boot_means)

def plot_event_study(events_df: pd.DataFrame, output_path: str):
    if events_df.empty:
        return
    # Encontra o menor comprimento da janela
    lens = [len(w) for w in events_df['window_returns']]
    if not lens:
        return
    max_len = min(lens)
    matrix = np.array([ret[:max_len] for ret in events_df['window_returns']])
    mean_returns = matrix.mean(axis=0)
    std_returns = matrix.std(axis=0)
    offset = len(mean_returns) // 2
    x_axis = np.arange(-offset, len(mean_returns) - offset)
    plt.figure(figsize=(12,5))
    plt.plot(x_axis, mean_returns, label='Média dos retornos acumulados (%)', linewidth=2)
    plt.fill_between(x_axis, mean_returns - std_returns, mean_returns + std_returns, alpha=0.3, label='±1 desvio')
    plt.axvline(x=0, color='red', linestyle='--', label='Evento (volume extremo)')
    plt.axhline(y=0, color='black', linewidth=0.5)
    plt.title('Event Study: Retorno Acumulado em Torno de Volume Extremo (>10x média)')
    plt.xlabel('Candles a partir do evento')
    plt.ylabel('Retorno acumulado (%)')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_path, dpi=100)
    plt.close()

def main():
    data_path = Path(r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_processado.parquet")
    df = pd.read_parquet(data_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    if 'maxima' in df.columns:
        df.rename(columns={'maxima': 'máxima', 'minima': 'mínima'}, inplace=True)
    
    df = add_volume_features(df, vol_lookback=50)
    split_date = df['datetime'].quantile(0.8)
    _, test = split_out_of_sample(df, split_date)
    
    print("=== EXTREME EVENT REGIME ENGINE ===")
    print("Threshold volume_rel > 10.0\n")
    
    events_test = extract_extreme_events(test, threshold=10.0, lookback=20, forward=20)
    print(f"Eventos extremos encontrados no teste: {len(events_test)}")
    
    if len(events_test) == 0:
        print("Nenhum evento extremo na amostra de teste. Não é possível validar robustez.")
        return
    
    # Event study gráfico
    plot_event_study(events_test, "graficos/extreme_event_study.png")
    print("Gráfico event study salvo em 'graficos/extreme_event_study.png'")
    
    # Desempenho futuro
    future_returns = events_test['future_ret_pct'].values
    expectancy = np.mean(future_returns)
    win_rate = np.mean(future_returns > 0)
    print(f"\n--- Desempenho após eventos extremos (OOS) ---")
    print(f"Expectancy (retorno percentual acumulado após 20 candles): {expectancy:.4f}%")
    print(f"Win rate: {win_rate:.2%}")
    
    # Bootstrap
    boot_means = bootstrap_extreme_trades(future_returns, n_bootstrap=10000)
    if len(boot_means) > 0:
        lower_95 = np.percentile(boot_means, 2.5)
        upper_95 = np.percentile(boot_means, 97.5)
        print(f"\n--- Bootstrap 10000 simulações ---")
        print(f"Média bootstrap: {np.mean(boot_means):.4f}%")
        print(f"Intervalo de confiança 95%: [{lower_95:.4f}%, {upper_95:.4f}%]")
        if lower_95 > 0:
            print("✅ Bootstrap sugere expectancy positiva com 95% de confiança.")
        else:
            print("❌ Bootstrap não rejeita expectativa zero ou negativa (ruído).")
    
    # Estabilidade temporal
    stability_df = time_split_stability(events_test, n_splits=3)
    print("\n--- Estabilidade temporal (split dos eventos por ordem cronológica) ---")
    print(stability_df.to_string(index=False))
    if len(stability_df) > 0 and (stability_df['expectancy_pct'] > 0).all():
        print("✅ Expectancy positiva em todos os splits (consistente).")
    else:
        print("⚠️ Expectancy oscila ou negativa em algum split (instável).")
    
    # Baseline
    test['future_ret_pct'] = (test['fechamento'].shift(-20) / test['fechamento'] - 1) * 100
    baseline_returns = test['future_ret_pct'].dropna()
    baseline_exp = baseline_returns.mean()
    print(f"\n--- Baseline (todos os candles, mesmo horizonte) ---")
    print(f"Expectancy baseline: {baseline_exp:.4f}%")
    if expectancy > baseline_exp:
        print("✅ Regime extremo supera baseline.")
    else:
        print("❌ Regime extremo não supera baseline.")
    
    # Salvar eventos
    events_test[['event_time', 'volume_rel', 'future_ret_pct']].to_csv("graficos/extreme_events.csv", index=False)
    print("\nEventos salvos em 'graficos/extreme_events.csv'")

if __name__ == "__main__":
    main()