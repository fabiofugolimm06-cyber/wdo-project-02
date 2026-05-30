# Risk Engine — v1 (Stage 17)

**Pacote:** `microstructure/risk/`  
**Testes:** `tests/test_risk_engine_v1.py`

---

## Papel no pipeline

```
MODEL → SIGNAL → RISK ENGINE → EXECUTION → BACKTEST
```

Camada de controle **antes** da execução simulada, sem alterar Execution, Backtest ou demais módulos.

---

## API

```python
from microstructure.risk import (
    calculate_position_size,
    check_daily_loss_limit,
    check_max_drawdown,
    risk_filter,
)
from microstructure.execution import simulate_execution

sizing = calculate_position_size(
    capital=100_000.0,
    risk_per_trade=0.01,   # 1% do capital por trade
    stop_loss_pct=0.01,    # stop 1% (alinha backtest v3)
)

daily = check_daily_loss_limit(current_pnl=-80.0, daily_loss_limit=-150.0)
dd = check_max_drawdown(current_drawdown=-0.05, max_drawdown_limit=-0.10)
allow = daily["risk_allowed"] and dd["risk_allowed"]

filtered = risk_filter(signals, allow_trading=allow)

exec_df, metrics = simulate_execution(
    filtered["signals"],
    initial_capital=100_000.0,
    position_size=sizing["position_size"],
)
```

---

## Funções

| Função | Retorno | Descrição |
|--------|---------|-----------|
| `calculate_position_size` | `{"position_size"}` | `risk_per_trade / stop_loss_pct` (anti divisão por zero) |
| `check_daily_loss_limit` | `{"risk_allowed"}` | PnL diário ≥ limite (limite ≤ 0) |
| `check_max_drawdown` | `{"risk_allowed"}` | DD atual ≥ limite (ambos ≤ 0) |
| `risk_filter` | `signals`, `trading_enabled`, `risk_allowed` | Zera sinais se trading bloqueado |

---

## Validações

| Parâmetro | Regra |
|-----------|--------|
| `capital` | > 0 |
| `risk_per_trade` | (0, 1] |
| `stop_loss_pct` | > 0 |
| `daily_loss_limit` | ≤ 0 (ex.: `-150`) |
| `max_drawdown_limit` | ≤ 0 (ex.: `-0.10`) |
| `current_drawdown` | ≤ 0 |
| `signals` | valores em `{-1, 0, 1}` |

---

## Compatibilidade Execution v1

- `risk_filter` preserva índice `pd.Series`
- `position_size` retornado alimenta `simulate_execution(..., position_size=...)`
- Sinais ML `{0, 1}` são subconjunto válido

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_risk_engine_v1.py -v -s
```

Saída esperada: `RISK ENGINE V1 OK`

---

## Roadmap (v2+)

- Seção `risk` em Strategy Config
- Integração em `run_full_pipeline` (opcional)
- Kill switch intraday / cooldown
- VaR e exposição agregada
