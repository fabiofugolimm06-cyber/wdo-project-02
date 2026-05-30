import pandas as pd
import numpy as np
from typing import Callable, Dict

def walk_forward_analysis(
    df: pd.DataFrame,
    strategy_func: Callable,
    train_days: int = 90,
    test_days: int = 30,
    step_days: int = 30,
    min_train_rows: int = 500
) -> Dict:
    df = df.sort_values('datetime').reset_index(drop=True)
    start = df['datetime'].min()
    end = df['datetime'].max()
    
    results = []
    current_train_start = start
    fold = 0
    
    while True:
        train_end = current_train_start + pd.Timedelta(days=train_days)
        test_start = train_end
        test_end = test_start + pd.Timedelta(days=test_days)
        
        if test_end > end:
            break
        
        train_mask = (df['datetime'] >= current_train_start) & (df['datetime'] < train_end)
        test_mask = (df['datetime'] >= test_start) & (df['datetime'] < test_end)
        
        if train_mask.sum() < min_train_rows or test_mask.sum() < 100:
            current_train_start += pd.Timedelta(days=step_days)
            continue
        
        train_df = df[train_mask].copy()
        test_df = df[test_mask].copy()
        
        params = strategy_func(train_df) if callable(strategy_func) else {}
        test_df = apply_strategy(test_df, params)
        
        from metrics_engine import calculate_metrics
        metrics = calculate_metrics(test_df)
        
        results.append({
            'fold': fold,
            'train_start': current_train_start,
            'train_end': train_end,
            'test_start': test_start,
            'test_end': test_end,
            'n_train': len(train_df),
            'n_test': len(test_df),
            'metrics': metrics
        })
        
        current_train_start += pd.Timedelta(days=step_days)
        fold += 1
    
    agg = {
        'mean_max_drawdown': np.mean([r['metrics']['max_drawdown'] for r in results]),
        'std_max_drawdown': np.std([r['metrics']['max_drawdown'] for r in results]),
        'mean_expectancy': np.mean([r['metrics']['expectancy_points'] for r in results]),
        'mean_profit_factor': np.mean([r['metrics']['profit_factor'] for r in results]),
        'oos_consistency': np.std([r['metrics']['expectancy_points'] for r in results]) / (abs(np.mean([r['metrics']['expectancy_points'] for r in results])) + 1e-9),
        'all_folds': results
    }
    return agg

def apply_strategy(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    df = df.copy()
    fast = params.get('fast', 7)
    slow = params.get('slow', 20)
    df['MM_fast'] = df['fechamento'].rolling(fast).mean()
    df['MM_slow'] = df['fechamento'].rolling(slow).mean()
    df['sinal'] = 0
    df.loc[df['MM_fast'] > df['MM_slow'], 'sinal'] = 1
    df.loc[df['MM_fast'] < df['MM_slow'], 'sinal'] = -1
    df['posicao'] = df['sinal'].shift(1).fillna(0)
    return df