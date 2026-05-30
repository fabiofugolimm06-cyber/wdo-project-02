import pandas as pd
import numpy as np

def calculate_metrics(trades):
    if len(trades) == 0:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'total_pnl': 0.0
        }
    df = pd.DataFrame(trades)
    wins = df[df['pnl'] > 0]
    losses = df[df['pnl'] < 0]
    total_pnl = df['pnl'].sum()
    win_rate = len(wins) / len(df) if len(df) > 0 else 0.0
    gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0.0
    gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 1.0
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else 0.0
    daily_pnl = df.groupby(pd.to_datetime(df['entry_time']).dt.date)['pnl'].sum()
    sharpe = daily_pnl.mean() / daily_pnl.std() * np.sqrt(252) if daily_pnl.std() != 0 else 0.0
    cumulative = df['pnl'].cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    max_drawdown = drawdown.min()
    return {
        'total_trades': len(df),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'total_pnl': total_pnl
    }
