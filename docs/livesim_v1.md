# Live Simulation Engine — v1 (Stage 20)

**Pacote:** `microstructure/livesim/`  
**Classe:** `LiveSimulationEngine`  
**Testes:** `tests/test_livesim_v1.py`

---

## Objetivo

Simular ambiente **streaming** bar a bar, sem lookahead, integrando Model v1, Risk, Paper Trading e Execution.

```
DATA STREAM → SIGNAL (ML) → RISK → PAPER TRADING → EXECUTION (resumo)
```

---

## API

```python
from microstructure.livesim import LiveSimulationEngine
from microstructure.strategy_config import get_default_config

engine = LiveSimulationEngine()
final_state = engine.run_stream(
    df,
    model,                    # LogisticRegression treinado offline
    get_default_config("wdo_live"),
    risk_engine={
        "daily_loss_limit": -1500.0,
        "max_drawdown_limit": -0.10,
    },
)
```

---

## Métodos

| Método | Descrição |
|--------|-----------|
| `run_stream(df, model, strategy_config, risk_engine?)` | Loop completo bar a bar |
| `step(bar_index)` | Uma barra: `emit_signal` → paper `update_position` → `on_signal` |
| `emit_signal()` | Features só com `df[:i+1]`; `predict_proba` + `generate_ml_signal` |
| `update_state(...)` | Atualiza `equity_curve` e posição |
| `log_event(type, payload)` | Append em `events` com timestamp |
| `get_state()` | Cópia do estado |

---

## Estado final

```python
{
    "current_position": 0,
    "equity_curve": [
        {"bar_index", "timestamp", "price", "equity", "current_pnl", "position"},
        ...
    ],
    "events": [
        {"type", "timestamp", "bar_index", "payload"},
        ...
    ],
}
```

Eventos típicos: `stream_start`, `bar`, `execution_summary`, `stream_end`.

---

## Anti-lookahead

- Features: `build_dataset(df.iloc[:bar_index + 1])` — só última linha usada
- Preço futuro alterado **não** muda `raw_signal` em barras anteriores (teste automatizado)

---

## Integrações (somente consumo; módulos não alterados)

| Stage | Uso |
|-------|-----|
| Model v1 | `predict_probabilities`, `generate_ml_signal` |
| Strategy Config | `price_col`, `ml_threshold`, execution/backtest params |
| Risk Engine | limites via `PaperTradingEngine` + `risk_filter` |
| Paper Trading v1 | `update_position`, `on_signal` por barra |
| Execution v1 | `execution_summary` ao fim do stream |

**Ordem por barra:** `update_position(price)` → `on_signal(signal)` (via Paper Trading).

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_livesim_v1.py -v -s
```

Saída esperada: `LIVE SIMULATION V1 OK`

---

## Roadmap (v2+)

- Feed assíncrono / fila de ticks
- Persistência de estado em `run_directory` (Run Manager)
- Re-treino online desligado por padrão
- Latência e clock de mercado
