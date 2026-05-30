# Paper Trading Engine — v1 (Stage 19)

**Pacote:** `microstructure/papertrading/`  
**Classe:** `PaperTradingEngine`  
**Testes:** `tests/test_papertrading_v1.py`

---

## Papel no pipeline

```
SIGNAL → RISK → PAPER TRADING → EXECUTION (comparação) → feedback
```

Simula posição aberta, PnL mark-to-market, custos e slippage (Strategy Config), com filtro de Risk Engine.

---

## Uso

```python
from microstructure.papertrading import PaperTradingEngine
from microstructure.strategy_config import get_default_config

engine = PaperTradingEngine(
    initial_capital=100_000.0,
    strategy_config=get_default_config("wdo_live"),
    daily_loss_limit=-150.0,
    max_drawdown_limit=-0.10,
)

engine.initialize_state()

for price, signal in zip(prices, signals):
    engine.update_position(price)
    engine.on_signal(signal)

state = engine.get_state()
```

---

## Métodos

| Método | Descrição |
|--------|-----------|
| `initialize_state()` | Reinicia estado |
| `update_position(price)` | Mark-to-market; stop/take profit automáticos |
| `on_signal(signal)` | Abre/fecha via {-1,0,1}; aplica `risk_filter` |
| `close_position(reason, price?)` | Fecha posição manual ou por regra |
| `get_state()` | Cópia do estado |

---

## Estado

```python
{
    "position": 0,           # -1, 0, 1
    "entry_price": None,
    "current_pnl": 0.0,
    "realized_pnl": 0.0,
    "unrealized_pnl": 0.0,
    "capital": 100_000.0,
    "equity_peak": ...,
    "current_drawdown": 0.0,
    "trades": [...],
    "last_price": ...,
    "position_units": 1.0,
    "trading_enabled": True,
    "bar_index": 0,
    "total_costs": 0.0,
}
```

Cada trade em `trades`: `entry_price`, `exit_price`, `position`, `trade_pnl`, `return_pct`, `reason`, `bar_index`.

---

## Integrações

| Módulo | Como |
|--------|------|
| **Strategy Config** | `cost_per_trade`, `slippage`, `stop_loss`, `take_profit`, `position_size` |
| **Risk Engine** | `check_daily_loss_limit`, `check_max_drawdown`, `risk_filter` em `on_signal` |
| **Execution v1** | Mesma semântica de sinal/posição; comparar com `simulate_execution` |

**Ordem recomendada por barra:** `update_position(price)` → `on_signal(signal)`.

---

## Motivos de fechamento

`signal_flat`, `signal_flip`, `stop_loss`, `take_profit`, `manual`

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_papertrading_v1.py -v -s
```

Saída esperada: `PAPER TRADING V1 OK`

---

## Roadmap (v2+)

- Persistência de estado em `run_directory`
- Feed de preços ao vivo
- Sincronização com broker / Profit
- Log estruturado por `run_id`
