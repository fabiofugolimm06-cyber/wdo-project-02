import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from walk_forward import walk_forward_analysis, apply_strategy
from oos_engine import split_out_of_sample
from cost_model import adjust_trade_costs
from regime_filter import add_regime_filter
from metrics_engine import calculate_metrics
from monte_carlo import monte_carlo_resample

def baseline_strategy(train_df: pd.DataFrame) -> dict:
    return {'fast': 7, 'slow': 20}

def add_time_filter(df: pd.DataFrame, start_hour: int = 10, end_hour: int = 12, end_minute: int = 30) -> pd.DataFrame:
    """Zera posições fora do horário permitido (ex: 10:00-12:30)"""
    df = df.copy()
    hour = df['datetime'].dt.hour
    minute = df['datetime'].dt.minute
    time_ok = ((hour >= start_hour) & (hour < end_hour)) | ((hour == end_hour) & (minute <= end_minute))
    if 'posicao' in df.columns:
        df['posicao'] = df['posicao'].where(time_ok, 0)
    return df

def main():
    data_path = r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_processado.parquet"
    
    print("Carregando dados...")
    df = pd.read_parquet(data_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    
    # Ajuste de nomes de colunas (se necessário)
    if 'maxima' in df.columns:
        df.rename(columns={'maxima': 'máxima', 'minima': 'mínima'}, inplace=True)
    
    split_date = df['datetime'].quantile(0.8)
    train, test = split_out_of_sample(df, split_date)
    print(f"Treino: {train['datetime'].min()} -> {train['datetime'].max()} ({len(train)} registros)")
    print(f"Teste: {test['datetime'].min()} -> {test['datetime'].max()} ({len(test)} registros)")
    
    # 1. Gera sinais da estratégia (posição bruta)
    test = apply_strategy(test, baseline_strategy(train))
    
    # 2. Aplica filtro de volatilidade (regime)
    test = add_regime_filter(test)
    
    # 3. Aplica filtro de horário (10:00-12:30)
    test = add_time_filter(test, start_hour=10, end_hour=12, end_minute=30)
    
    metrics_raw = calculate_metrics(test)
    print("\n=== Métricas OOS (com filtros) ===")
    for k, v in metrics_raw.items():
        if isinstance(v, float):
            print(f"{k}: {v:.4f}")
        else:
            print(f"{k}: {v}")
    
    print("\n=== Executando Walk-Forward (baseline, sem filtros) ===")
    wf_results = walk_forward_analysis(
        df,
        strategy_func=baseline_strategy,
        train_days=90,
        test_days=30,
        step_days=30
    )
    print(f"Mean Max Drawdown OOS: {wf_results['mean_max_drawdown']:.2%}")
    print(f"Std Max Drawdown OOS: {wf_results['std_max_drawdown']:.2%}")
    print(f"Mean Expectancy: {wf_results['mean_expectancy']:.2f} pontos")
    print(f"OOS Consistency (CV): {wf_results['oos_consistency']:.2f}")

if __name__ == "__main__":
    main()