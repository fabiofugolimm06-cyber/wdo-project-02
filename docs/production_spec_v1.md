# Production Output Spec — v1 (Stage 21)

**Pacote:** `microstructure/production/`  
**Testes:** `tests/test_production_spec_v1.py`

Contrato único de saída do WDO PROJECT 02 para produção (Profit NTSL, bridge V6, API futura).

---

## Objetivo

```
Decision Engine → Production Spec → (NTSL / Bridge JSON / API)
```

Camada **somente exportação** — não altera `execution_bridge`, `decision_engine` nem backtests.

---

## ProductionSpecV1

```python
from microstructure.production import ProductionSpecV1
from microstructure.strategy_config import get_default_config

spec = ProductionSpecV1(strategy_config=get_default_config("wdo_prod"))

row = spec.export_signal({
    "timestamp": "2024-08-01 09:15:00",
    "signal": 1,
    "confidence": 0.85,
    "mode": "hybrid",
    "price": 5450.0,
})

ntsl_text = spec.to_ntsl([row])
json_str = spec.to_bridge_json([row])
spec.validate_output(row)
```

---

## Contrato `export_signal`

```python
{
    "timestamp": "2024-08-01 09:15:00",
    "symbol": "WDO",
    "signal": 1,              # ∈ {-1, 0, 1}
    "confidence": 0.85,       # [0, 1]
    "mode": "hybrid",         # signal | ml | hybrid
    "risk": {
        "position_size": 1.0,
        "stop_loss": 0.01,
        "take_profit": 0.02,
    },
    "price": 5450.0,          # opcional
}
```

`risk` deriva de `strategy_config` (backtest + execution) ou de `risk_defaults` no construtor.

---

## NTSL — `to_ntsl(signal_series)`

Texto comentado, rule-based, sem dependências de ML:

```text
// WDO Production Spec — NTSL export v1 (WDO)
// TIMESTAMP | SIGNAL | ACTION | PRICE | MODE | CONFIDENCE
// 2024-08-01 09:15:00 | 1 | BUY | 5450.0000 | hybrid | 0.8500
```

Compatível em espírito com `execution_bridge.export_to_ntsl` (mesmas ações BUY/SELL/FLAT).

---

## Bridge JSON — `to_bridge_json(signal_series)`

Lista JSON ordenada por `timestamp` (determinística):

```json
[
  {
    "timestamp": "2024-08-01 09:15:00",
    "symbol": "WDO",
    "signal": 1,
    "action": "BUY",
    "confidence": 0.85,
    "mode": "hybrid",
    "price": 5450.0,
    "risk": { "position_size": 1.0, "stop_loss": 0.01, "take_profit": 0.02 }
  }
]
```

Compatível com `export_to_bridge_format` + `send_to_execution_layer` (campos mínimos `timestamp`, `signal`).

---

## `validate_output`

Garante:

- timestamps monotônicos (lista)
- sem NaN em `confidence` / `price` / `risk`
- `signal ∈ {-1, 0, 1}`
- `risk.position_size`, `stop_loss`, `take_profit` > 0

---

## Integração com Execution Bridge

```python
bridge = ExecutionBridge(mode="export")
# ... process_signal ...

spec = ProductionSpecV1()
records = [
    spec.export_signal({
        "timestamp": e["timestamp"],
        "signal": e["signal"],
        "price": e["price"],
    })
    for e in bridge.get_state()["execution_log"]
]
prod_json = spec.to_bridge_json(records)
```

---

## API-ready (futuro)

O dict de `export_signal` é o payload estável para REST/WebSocket; `to_bridge_json` é a serialização em lote.

---

**PRODUCTION SPEC V1 OK**
