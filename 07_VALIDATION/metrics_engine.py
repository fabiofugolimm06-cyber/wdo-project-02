import pandas as pd
import numpy as np

def calculate_metrics(df: pd.DataFrame) -> dict:
    if 'pnl_points' in df.columns and 'entry_time' in df.columns:
        trades = df.dropna(subset=['pnl_points']).copy()
        if len(trades) == 0:
            return _empty_metrics()
        equity = (1 + trades['pnl_points'] / 10000).cumprod()
        rets = equity.pct_change().dropna()
        max_dd = (equity.cummax() - equity).max() / equity.cummax().max()
        expectancy = trades['pnl_points'].mean()
        gross_profit = trades[trades['pnl_points'] > 0]['pnl_points'].sum()
        gross_loss = abs(trades[trades['pnl_points'] < 0]['pnl_points'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else np.inf
        sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() != 0 else 0
        exposure = (trades['exit_time'] - trades['entry_time']).sum().total_seconds() / (trades['exit_time'].max() - trades['entry_time'].min()).total_seconds() if len(trades) > 1 else 0
        avg_duration = (trades['exit_time'] - trades['entry_time']).mean().total_seconds()
        win_rate = (trades['pnl_points'] > 0).mean()
    else:
        df = df.copy()
        df['ret'] = df['fechamento'].pct_change()
        df['ret_estrategy'] = df['posicao'].shift(1) * df['ret']
        equity = (1 + df['ret_estrategy']).cumprod()
        rets = df['ret_estrategy'].dropna()
        if rets.std() == 0:
            return _empty_metrics()
        max_dd = (equity.cummax() - equity).max() / equity.cummax().max()
        expectancy = rets.mean() * 10000
        profit_factor = np.nan
        sharpe = rets.mean() / rets.std() * np.sqrt(252 * 1440)
        exposure = (df['posicao'] != 0).mean()
        avg_duration = np.nan
        win_rate = (df['ret_estrategy'] > 0).mean()
        trades = pd.DataFrame()
    
    return {
        'max_drawdown': max_dd,
        'expectancy_points': expectancy,
        'profit_factor': profit_factor,
        'sharpe_ratio': sharpe,
        'exposure': exposure,
        'avg_trade_duration_sec': avg_duration,
        'win_rate': win_rate,
        'total_trades': len(trades) if not trades.empty else (df['posicao'].diff().abs().sum() / 2)
    }

def _empty_metrics():
    return {
        'max_drawdown': 0,
        'expectancy_points': 0,
        'profit_factor': 0,
        'sharpe_ratio': 0,
        'exposure': 0,
        'avg_trade_duration_sec': 0,
        'win_rate': 0,
        'total_trades': 0
    }
