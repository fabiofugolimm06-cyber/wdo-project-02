# Execution Engine — v1 (Stage 09)

**Pacote:** `microstructure/execution/`  
**Módulo:** `simulator.py`  
**Testes:** `tests/test_execution_v1.py`

---

## Papel no pipeline

Camada de **execução simulada**, separada do backtest (v1/v2/v3).

```
DATA → FEATURES → SIGNALS → EXECUTION
```

Research ML (paralelo, sem substituir sinais de trading):

```
DATA → FEATURES → LABELS → MODEL → (opcional) sinais ML → EXECUTION
```

**Não altera:** `features/`, `signal/`, `labeling/`, `model/`, `walkforward`, `purged_kfold`, `backtest/`.

---

## API

```python
from microstructure.features.datasets import build_dataset
from microstructure.signal.signal_engine import generate_signals
from microstructure.execution import simulate_execution

X = build_dataset(df)
X = generate_signals(X)

exec_df, metrics = simulate_execution(
    X["signal"],
    initial_capital=100_000.0,
    position_size=1.0,
)
```

---

## Regras de posição

| `signal` | `current_position` |
|----------|-------------------|
| `1` | `+position_size` (comprado) |
| `-1` | `-position_size` (vendido) |
| `0` | `0` (flat) |

---

## Colunas do DataFrame

| Coluna | Descrição |
|--------|-----------|
| `signal` | Sinal de entrada |
| `current_position` | Posição alvo na barra |
| `position_changes` | Δ posição vs barra anterior (primeira barra vs 0) |
| `executed_orders` | `1` se houve ordem (`position_changes != 0`) |
| `gross_exposure` | `abs(current_position) * initial_capital` |

---

## Métricas

```python
{
    "num_orders": int,       # soma de executed_orders
    "long_entries": int,     # entradas em posição comprada
    "short_entries": int,    # entradas em posição vendida
    "flat_periods": int,     # barras em flat
}
```

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_execution_v1.py -v -s
```

Saída esperada: `EXECUTION V1 OK`

---

## Roadmap (v2+)

- Slippage e custos na execução
- Lag de execução (sinal t → ordem t+1)
- Integração com broker / Profit (fora do escopo v1)
- PnL mark-to-market (permanece no backtest)
