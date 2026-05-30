SLIPPAGE_POINTS = 0.5
SPREAD_POINTS = 0.5
COMMISSION_PER_CONTRACT = 0.20
FEES_B3_PER_CONTRACT = 0.10

def total_cost_per_contract() -> float:
    return COMMISSION_PER_CONTRACT + FEES_B3_PER_CONTRACT

def apply_slippage(price: float, side: str) -> float:
    if side == 'long':
        return price + SLIPPAGE_POINTS
    else:
        return price - SLIPPAGE_POINTS

def apply_spread(price: float, side: str) -> float:
    if side == 'long':
        return price + SPREAD_POINTS
    else:
        return price - SPREAD_POINTS

def adjust_trade_costs(
    entry_price: float,
    exit_price: float,
    side: str,
    n_contracts: int = 1
):
    entry_adj = apply_slippage(entry_price, side)
    exit_adj = apply_slippage(exit_price, 'short' if side == 'long' else 'long')
    total_cost_reais = total_cost_per_contract() * n_contracts
    return entry_adj, exit_adj, total_cost_reais
