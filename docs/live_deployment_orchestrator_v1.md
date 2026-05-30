# Live Deployment Orchestrator — v1 (Stage 23)

**Pacote:** `microstructure/live/live_deployment_orchestrator_v1.py`  
**Testes:** `tests/test_live_deployment_orchestrator_v1.py`

Orquestração contínua do pipeline WDO em produção/simulação.

---

## Fluxo

```
EVENT STREAM → DECISION → RISK GUARDIAN → PRODUCTION SPEC → EXECUTION → STATE
```

Somente composição — **sem** recálculo de features nem lógica de decisão duplicada.

---

## LiveDeploymentOrchestratorV1

```python
from microstructure.core import run_decision_pipeline
from microstructure.execution_bridge import ExecutionBridge
from microstructure.live import LiveDeploymentOrchestratorV1
from microstructure.production import ProductionSpecV1
from microstructure.risk import RiskGuardianV1
from microstructure.strategy_config import get_default_config

cfg = get_default_config("wdo_deploy")
orch = LiveDeploymentOrchestratorV1(
    decision_engine=run_decision_pipeline,
    risk_guardian=RiskGuardianV1(max_daily_loss=-150.0),
    execution_bridge=ExecutionBridge(cfg, mode="paper"),
    production_spec=ProductionSpecV1(strategy_config=cfg),
    mode="paper",  # paper | export | live | livesim
)

result = orch.run_stream(df_ohlcv)
log = result["log"]
state = result["state"]
```

### Métodos

| Método | Descrição |
|--------|-----------|
| `on_new_market_data(bar)` | Uma barra (dict ou Series) |
| `run_stream(df \| iterator)` | Loop temporal completo |
| `get_state()` | mode, status, pnl, positions, risk_state |
| `reset()` | Reinicia sessão |

---

## Log por barra

Cada entrada contém:

- `signal` — sinal final aprovado
- `decision` — resumo do decision engine
- `risk_action` — saída do RiskGuardian (`blocked`, `reason`, …)
- `production` — contrato `ProductionSpecV1`
- `execution_action` — entrada do bridge ou `skipped`

---

## Fail-safe

| Condição | Ação |
|----------|------|
| Risk guardian bloqueia | **Não** chama `execution_bridge` |
| Exceção / estado inválido | `status=halted`, STOP |
| Timestamp fora de ordem | HALT seguro |

---

## Modos

| Modo | Uso |
|------|-----|
| `paper` | Default — `ExecutionBridge` + paper trading |
| `export` | Log + export NTSL/JSON |
| `live` | Stub live |
| `livesim` | Mesmo pipeline + `livesim_events` no estado |

---

## Integração

Componentes existentes são **injetados**, não alterados:

- `decision_engine_v1` → callable (`run_decision_pipeline`)
- `risk_guardian_v1` → `evaluate` / `update_state`
- `execution_bridge_v1` → `process_signal`
- `production_spec_v1` → `export_signal`
- Paper via bridge `mode="paper"`

---

**LIVE DEPLOYMENT ORCHESTRATOR V1 OK**
