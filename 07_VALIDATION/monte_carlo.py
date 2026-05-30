import numpy as np
import pandas as pd

def monte_carlo_resample(trades: pd.DataFrame, n_simulations: int = 1000, capital_points: float = 10000) -> dict:
    if trades.empty or len(trades) < 10:
        return {'max_dd_median': 0, 'max_dd_95pc': 0, 'expectancy_median': 0, 'expectancy_5pc': 0}
    
    pnl_array = trades['pnl_points'].values
    n = len(pnl_array)
    
    simulated_max_dd = []
    simulated_expectancy = []
    
    for _ in range(n_simulations):
        sample = np.random.choice(pnl_array, size=n, replace=True)
        equity = capital_points + np.cumsum(sample)
        equity_curve = equity / capital_points
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (running_max - equity_curve) / running_max
        simulated_max_dd.append(np.max(drawdown))
        simulated_expectancy.append(np.mean(sample))
    
    return {
        'max_dd_median': np.median(simulated_max_dd),
        'max_dd_95pc': np.percentile(simulated_max_dd, 95),
        'expectancy_median': np.median(simulated_expectancy),
        'expectancy_5pc': np.percentile(simulated_expectancy, 5)
    }
