# Reporting & Performance Analytics — v1 (Stage 11)

**Pacote:** `microstructure/reporting/`  
**Função:** `generate_performance_report(backtest_result)`  
**Testes:** `tests/test_reporting_v1.py`

---

## Papel no pipeline

```
… → BACKTEST (v3) → REPORTING
```

Consolida o resultado de `run_backtest_v3()` em um relatório padronizado, **sem alterar** backtest nem outros módulos.

---

## Uso

```python
from microstructure.backtest.engine_v3 import run_backtest_v3
from microstructure.reporting import generate_performance_report

bt = run_backtest_v3(df, signals, price_col="fechamento")
report = generate_performance_report(bt)
```

---

## Entrada

Dict retornado por `run_backtest_v3()`:

| Chave | Uso |
|-------|-----|
| `metrics` | total_return, sharpe, max_drawdown, win_rate, avg_trade_return, completed_trades |
| `trades` | profit_factor (soma ganhos / \|soma perdas\|) |
| `df` | número de barras → annualized_return |

---

## Saída (9 métricas)

```python
{
    "total_return": float,
    "annualized_return": float,   # (1 + total_return)^(252/n) - 1
    "sharpe": float,              # herdado do backtest v3
    "max_drawdown": float,
    "calmar_ratio": float,        # annualized_return / |max_drawdown|
    "win_rate": float,
    "num_trades": int,            # completed_trades (fallback num_trades)
    "avg_trade_return": float,
    "profit_factor": float,       # inf se não houver perdas e houver ganhos
}
```

---

## Fórmulas v1

| Métrica | Definição |
|---------|-----------|
| `annualized_return` | `(1 + total_return)^(252 / n_bars) - 1` |
| `calmar_ratio` | `annualized_return / abs(max_drawdown)` |
| `profit_factor` | `Σ retornos positivos / \|Σ retornos negativos\|` (por trade) |

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_reporting_v1.py -v -s
```

Saída esperada: `REPORTING V1 OK`

---

## Integração E2E (opcional)

Após `run_full_pipeline`, rodar backtest completo e reportar:

```python
from microstructure.pipeline import run_full_pipeline
# ou bt = run_backtest_v3(...)
# report = generate_performance_report(bt)
```

Roadmap v2: export HTML/CSV, equity curve plots, comparação multi-run.
