# Live Orchestrator v1 — Bar-by-Bar Engine

**Módulo:** `microstructure/live/live_orchestrator_v1.py`  
**Classe:** `LiveOrchestratorV1`  
**Testes:** `tests/test_live_orchestrator_v1.py`

---

## Objetivo

Simular **mercado em tempo real** (bar-by-bar), conectando:

```
DATA STREAM → DECISION ENGINE → RISK → EXECUTION BRIDGE → LOG
```

Último passo antes de produção real (Profit / V6).

---

## Uso

```python
from microstructure.live import LiveOrchestratorV1, RiskFilterAdapter
from microstructure.execution_bridge import ExecutionBridge

orch = LiveOrchestratorV1(
    decision_engine=None,              # default: run_decision_pipeline
    risk_engine=RiskFilterAdapter(),
    execution_bridge=ExecutionBridge(mode="export"),
)

result = orch.run(df, mode="signal_only")
log = result["log"]
stats = result["final_state"]
```

---

## Fluxo por barra `t`

1. `slice_df = df.iloc[:t+1]` — **sem dados futuros**
2. `run_decision_pipeline(slice_df, mode=...)`
3. `signal = decision["signals"].iloc[-1]`
4. `risk_engine.filter(signal)` (opcional)
5. `execution_bridge.process_signal(signal, price, timestamp)` (opcional)
6. Append ao `log`

---

## Retorno

```python
{
    "log": pd.DataFrame,  # timestamp, signal, price, mode, bar_index
    "final_state": {
        "total_signals": int,
        "longs": int,
        "shorts": int,
        "flat": int,
    },
}
```

---

## Garantias

| Regra | Como |
|-------|------|
| Sem lookahead | Slice até `t` inclusive apenas |
| Sem shuffle | Loop `t = 0 .. n-1` |
| Determinístico | Mesmo `df` → mesmo `log` |
| Sinais válidos | `{-1, 0, 1}` |

---

## Interfaces opcionais

| Componente | Contrato |
|------------|----------|
| `decision_engine` | Callable `(slice_df, mode=..., **kwargs) -> dict` |
| `risk_engine` | Objeto com `.filter(signal) -> int` (`RiskFilterAdapter`) |
| `execution_bridge` | Objeto com `.process_signal(signal, price, timestamp)` |

---

## Integrações

- **Decision Engine v1** — `run_decision_pipeline` (default)
- **Risk Engine v1** — via `RiskFilterAdapter`
- **Execution Bridge v1** — `ExecutionBridge`

---

## Performance

Cada barra reconstrói features + decisão (`O(n²)` no número de barras). Adequado para **simulação e validação**; produção pode otimizar com cache incremental (v2).

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_live_orchestrator_v1.py -v -s
```

Saída: `LIVE ORCHESTRATOR V1 OK`

---

## Roadmap (v2+)

- Cache de features incrementais
- Feed ao vivo (socket / arquivo tail)
- Persistência de log no `run_directory`
- Hook para paper trading engine completo
