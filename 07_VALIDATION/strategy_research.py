import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from walk_forward import walk_forward_analysis, apply_strategy
from oos_engine import split_out_of_sample
from cost_model import adjust_trade_costs, SLIPPAGE_POINTS, COMMISSION_PER_CONTRACT, FEES_B3_PER_CONTRACT
from regime_filter import add_regime_filter
from metrics_engine import calculate_metrics
from monte_carlo import monte_carlo_resample

from strategies import (
    BreakoutDonchian20,
    BollingerMeanReversion20,
    TimeSessionBiasStrategy,
    BreakoutDonchianWithVolume
)
from strategy_base import StrategyBase

def backtest_strategy_with_filters(
    df: pd.DataFrame, 
    strategy: StrategyBase,
    apply_regime: bool = True,
    apply_time_filter: bool = False,
    start_hour: int = 10,
    end_hour: int = 12,
    end_minute: int = 30
) -> pd.DataFrame:
    df = df.copy()
    df = strategy.generate_signals(df)
    if apply_regime:
        df = add_regime_filter(df)
    if apply_time_filter:
        hour = df['datetime'].dt.hour
        minute = df['datetime'].dt.minute
        time_ok = ((hour >= start_hour) & (hour < end_hour)) | ((hour == end_hour) & (minute <= end_minute))
        df['posicao'] = df['posicao'].where(time_ok, 0)
    df['ret'] = df['fechamento'].pct_change()
    df['ret_estrategy'] = df['posicao'].shift(1) * df['ret']
    return df

def evaluate_strategy(
    df: pd.DataFrame,
    strategy: StrategyBase,
    train_test_split: float = 0.8,
    apply_regime: bool = True,
    apply_external_time_filter: bool = False,
    walk_forward_params: dict = None
) -> Dict:
    df = df.sort_values('datetime').reset_index(drop=True)
    split_idx = int(len(df) * train_test_split)
    train = df.iloc[:split_idx].copy()
    test = df.iloc[split_idx:].copy()
    test_backtest = backtest_strategy_with_filters(
        test, strategy, 
        apply_regime=apply_regime,
        apply_time_filter=apply_external_time_filter
    )
    metrics = calculate_metrics(test_backtest)
    if walk_forward_params:
        wf_results = simple_walk_forward(df, strategy, train_days=90, test_days=30, step_days=30)
    else:
        wf_results = {}
    return {
        'strategy_name': strategy.name,
        'params': strategy.params,
        'oos_metrics': metrics,
        'walk_forward': wf_results,
        'backtest_df': test_backtest
    }

def simple_walk_forward(df: pd.DataFrame, strategy: StrategyBase, train_days: int = 90, test_days: int = 30, step_days: int = 30) -> Dict:
    df = df.sort_values('datetime').reset_index(drop=True)
    start = df['datetime'].min()
    end = df['datetime'].max()
    results = []
    current_train_start = start
    while True:
        train_end = current_train_start + pd.Timedelta(days=train_days)
        test_start = train_end
        test_end = test_start + pd.Timedelta(days=test_days)
        if test_end > end:
            break
        train_mask = (df['datetime'] >= current_train_start) & (df['datetime'] < train_end)
        test_mask = (df['datetime'] >= test_start) & (df['datetime'] < test_end)
        if train_mask.sum() < 100 or test_mask.sum() < 50:
            current_train_start += pd.Timedelta(days=step_days)
            continue
        test_df = df[test_mask].copy()
        test_df = strategy.generate_signals(test_df)
        metrics = calculate_metrics(test_df)
        results.append({
            'test_start': test_start,
            'test_end': test_end,
            'max_drawdown': metrics['max_drawdown'],
            'expectancy': metrics['expectancy_points'],
            'profit_factor': metrics['profit_factor']
        })
        current_train_start += pd.Timedelta(days=step_days)
    if not results:
        return {}
    return {
        'mean_max_drawdown': np.mean([r['max_drawdown'] for r in results]),
        'std_max_drawdown': np.std([r['max_drawdown'] for r in results]),
        'mean_expectancy': np.mean([r['expectancy'] for r in results]),
        'consistency': np.std([r['expectancy'] for r in results]) / (abs(np.mean([r['expectancy'] for r in results])) + 1e-9),
        'n_folds': len(results)
    }

def rank_strategies(results_list: List[Dict]) -> pd.DataFrame:
    df_rank = pd.DataFrame(results_list)
    df_rank['expectancy'] = df_rank['oos_metrics'].apply(lambda x: x['expectancy_points'])
    df_rank['max_dd'] = df_rank['oos_metrics'].apply(lambda x: x['max_drawdown'])
    df_rank['consistency'] = df_rank['walk_forward'].apply(lambda x: x.get('consistency', np.nan) if x else np.nan)
    exp_min, exp_max = df_rank['expectancy'].min(), df_rank['expectancy'].max()
    dd_min, dd_max = df_rank['max_dd'].min(), df_rank['max_dd'].max()
    cv_min, cv_max = df_rank['consistency'].min(), df_rank['consistency'].max()
    expectancy_norm = (df_rank['expectancy'] - exp_min) / (exp_max - exp_min + 1e-9)
    dd_norm = 1 - (df_rank['max_dd'] - dd_min) / (dd_max - dd_min + 1e-9)
    consistency_norm = 1 - (df_rank['consistency'] - cv_min) / (cv_max - cv_min + 1e-9)
    df_rank['score'] = (expectancy_norm * 0.5) + (dd_norm * 0.3) + (consistency_norm * 0.2)
    df_rank = df_rank.sort_values('score', ascending=False).reset_index(drop=True)
    return df_rank

def plot_equity_curves(results_list: List[Dict], output_path: str = "graficos/strategy_equity_curves.png"):
    plt.figure(figsize=(12, 6))
    for res in results_list:
        name = res['strategy_name']
        test_df = res.get('backtest_df')
        if test_df is not None and 'ret_estrategy' in test_df.columns:
            equity = (1 + test_df['ret_estrategy']).cumprod()
            plt.plot(test_df['datetime'], equity, label=name, linewidth=1)
    plt.title('Equity Curves Comparativas - Estratégias (OOS com filtros)')
    plt.xlabel('Data')
    plt.ylabel('Equity (base=1)')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_path, dpi=100)
    plt.close()
    print(f"Gráfico salvo em {output_path}")

def main():
    data_path = r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_processado.parquet"
    df = pd.read_parquet(data_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    if 'maxima' in df.columns:
        df.rename(columns={'maxima': 'máxima', 'minima': 'mínima'}, inplace=True)
    
    # Lista de estratégias a comparar
    strategies = [
        BreakoutDonchian20(),
        BollingerMeanReversion20(),
        BreakoutDonchianWithVolume(),   # NOVA ESTRATÉGIA
        # TimeSessionBiasStrategy()     # (opcional, removido para focar)
    ]
    
    all_results = []
    for strat in strategies:
        print(f"\n--- Testando estratégia: {strat.name} ---")
        # Aplica filtro de horário externo apenas para estratégias que não têm horário interno
        apply_external_time = not isinstance(strat, TimeSessionBiasStrategy)
        result = evaluate_strategy(
            df,
            strat,
            apply_regime=True,
            apply_external_time_filter=apply_external_time,
            walk_forward_params={'train_days': 90, 'test_days': 30, 'step_days': 30}
        )
        all_results.append(result)
        print(f"  Expectancy OOS: {result['oos_metrics']['expectancy_points']:.4f}")
        print(f"  Max Drawdown OOS: {result['oos_metrics']['max_drawdown']:.2%}")
        if result['walk_forward']:
            print(f"  WF Consistency: {result['walk_forward'].get('consistency', np.nan):.2f}")
    
    ranking_df = rank_strategies(all_results)
    print("\n" + "="*60)
    print("RANKING FINAL DAS ESTRATÉGIAS")
    print("="*60)
    print(ranking_df[['strategy_name', 'expectancy', 'max_dd', 'consistency', 'score']].to_string(index=False))
    
    ranking_df.to_csv("graficos/strategy_ranking.csv", index=False)
    print("\nTabela de ranking salva em 'graficos/strategy_ranking.csv'")
    
    plot_equity_curves(all_results, "graficos/strategy_equity_curves.png")
    
    detailed = []
    for res in all_results:
        row = {
            'Strategy': res['strategy_name'],
            'Params': str(res['params']),
            'OOS_Expectancy_points': res['oos_metrics']['expectancy_points'],
            'OOS_Max_Drawdown': res['oos_metrics']['max_drawdown'],
            'OOS_Sharpe': res['oos_metrics']['sharpe_ratio'],
            'OOS_Exposure': res['oos_metrics']['exposure'],
            'OOS_Win_Rate': res['oos_metrics']['win_rate'],
            'OOS_Total_Trades': res['oos_metrics']['total_trades'],
            'WF_Mean_Expectancy': res['walk_forward'].get('mean_expectancy', np.nan) if res['walk_forward'] else np.nan,
            'WF_Consistency': res['walk_forward'].get('consistency', np.nan) if res['walk_forward'] else np.nan,
        }
        detailed.append(row)
    pd.DataFrame(detailed).to_csv("graficos/strategy_detailed_metrics.csv", index=False)
    print("Métricas detalhadas salvas em 'graficos/strategy_detailed_metrics.csv'")

if __name__ == "__main__":
    main()