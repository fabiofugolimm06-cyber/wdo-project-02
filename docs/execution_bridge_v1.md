# Execution Abstraction Layer — v1 (Stage 21)

**Pacote:** `microstructure/execution_bridge/`  
**Testes:** `tests/test_execution_bridge_v1.py`

Ponte entre o pipeline quant e destinos operacionais (**Profit NTSL**, **V6**, **live stub**).

---

## Objetivo

```
SIGNAL → RISK → EXECUTION BRIDGE → (NTSL / V6 JSON / LIVE stub) → Profit Pro
```

Uma API, vários formatos de saída — **sem ordens reais** no v1.

---

## ExecutionBridge

```python
from microstructure.execution_bridge import ExecutionBridge
from microstructure.strategy_config import get_default_config

bridge = ExecutionBridge(
    get_default_config("wdo_prod"),
    mode="paper",   # "paper" | "live" | "export"
)

bridge.process_signal(signal=1, price=5450.0, timestamp="2024-07-01 09:15:00")
state = bridge.get_state()
```

### Modos

| Modo | Comportamento |
|------|----------------|
| `paper` | Delega a `PaperTradingEngine` (update + on_signal) |
| `export` | Só `execution_log` + exportadores |
| `live` | Log + `send_to_execution_layer` (stub) |

### Métodos

| Método | Descrição |
|--------|-----------|
| `process_signal(signal, price, timestamp)` | Risk filter + log + modo |
| `get_state()` | `execution_log`, `risk_snapshot`, `paper_state` |
| `reset()` | Reinicia sessão |
| `export_ntsl()` / `export_v6_bridge()` | Export a partir do log |

---

## execution_log

```python
{
    "timestamp": "2024-07-01 09:15:00",
    "signal": 1,
    "raw_signal": 1,
    "action": "BUY",      # BUY | SELL | FLAT
    "mode": "export",
    "price": 5450.0,
    "sequence": 1,
    "risk_allowed": True,
}
```

---

## Exportadores

### (A) NTSL — `export_to_ntsl(signals_df)`

Texto comentado, uma linha por barra:

```text
// TIMESTAMP | SIGNAL | ACTION | PRICE
// 2024-07-01 09:15:00 | 1 | BUY | 5450.0000
```

### (B) V6 Bridge — `export_to_bridge_format(signals_df)`

```json
{
  "timestamp": "2024-07-01 09:15:00",
  "signal": 1,
  "action": "BUY",
  "price": 5450.0,
  "risk": { "risk_allowed": true, ... }
}
```

### (C) Live stub — `send_to_execution_layer(packet)`

Retorna `{ "status": "logged_only", "message": "...", "packet": {...} }` — **não envia ordem**.

---

## Regras

- Timestamps **monotônicos** (erro se voltar no tempo)
- `risk_filter` + limites de Strategy Config / construtor
- Determinístico (mesma sequência → mesmo log)
- Sem lookahead (cada `process_signal` é um evento pontual)

---

## Integração

| Módulo | Uso |
|--------|-----|
| Strategy Config v1 | Parâmetros + validação |
| Risk Engine v1 | `risk_filter`, limites diário / DD |
| Paper Trading v1 | Modo `paper` |
| Live Simulation v1 | Pode chamar `process_signal` bar a bar |

**Não altera:** `microstructure/execution/` (simulate_execution v1).

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_execution_bridge_v1.py -v -s
```

Saída: `EXECUTION BRIDGE V1 OK`

---

## Roadmap (v2+)

- Escrever `bridge_signals.json` no `run_directory` (Run Manager)
- NTSL com blocos reais (Buy/Sell)
- Webhook / arquivo watch para V6
- Live real via API corretora (fora do stub)
