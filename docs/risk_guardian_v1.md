# Risk Guardian System — v1 (Stage 22)

**Pacote:** `microstructure/risk/risk_guardian_v1.py`  
**Integração:** `microstructure/risk/guardian_integration_v1.py`  
**Testes:** `tests/test_risk_guardian_v1.py`

Circuit breaker global **antes** de qualquer execução (paper ou live).

---

## Objetivo

```
Decision → RiskGuardian → (Paper / ExecutionBridge / Live Orchestrator)
```

Nenhum trade direcional chega à execução sem passar pelo guardian.  
Módulos existentes **não são alterados** — apenas wrappers de composição.

---

## RiskGuardianV1

```python
from microstructure.risk import RiskGuardianV1

guardian = RiskGuardianV1(
    max_daily_loss=-150.0,
    max_drawdown=-0.10,
    max_consecutive_losses=3,
    max_position_exposure=1.0,
    cooldown_after_loss=5,
)

out = guardian.evaluate(
    state={"daily_pnl": -10.0, "current_drawdown": -0.02, "exposure": 0.0},
    proposed_signal={"signal": 1, "risk": {"position_size": 1.0}},
)
# out["approved_signal"], out["reason"], out["blocked"]

guardian.update_state({"pnl": -20.0, "is_loss": True})
guardian.force_stop()  # kill switch manual
```

### Regras

| Regra | Comportamento |
|-------|----------------|
| Max daily loss | PnL ≤ limite → bloqueia + halt |
| Max drawdown | DD ≤ limite → HALT total |
| Loss streak | N perdas → cooldown (barras) |
| Exposure | Projeto de tamanho > limite → bloqueia |
| Kill switch | `force_stop()` → bloqueia direcional |
| Fail-safe | Entrada inválida → sinal 0 |

Sinal **0 (flat)** é sempre permitido quando não há kill/halt.

---

## Integração (sem alterar módulos base)

### Live Orchestrator

```python
from microstructure.risk import RiskGuardianV1, RiskGuardianFilterAdapter
from microstructure.live import LiveOrchestratorV1

guardian = RiskGuardianV1()
orch = LiveOrchestratorV1(risk_engine=RiskGuardianFilterAdapter(guardian))
```

### Execution Bridge

```python
from microstructure.execution_bridge import ExecutionBridge
from microstructure.risk import GuardedExecutionBridge, RiskGuardianV1

inner = ExecutionBridge(mode="export")
bridge = GuardedExecutionBridge(inner, RiskGuardianV1(max_daily_loss=-150.0))
bridge.process_signal(1, 5450.0, "2024-10-01 09:15:00")
```

### Decision Engine

```python
from microstructure.risk import guarded_run_decision_pipeline, RiskGuardianV1

decision = guarded_run_decision_pipeline(guardian, df, mode="signal_only")
```

### Paper Trading

```python
from microstructure.papertrading import PaperTradingEngine
from microstructure.risk import GuardedPaperTradingEngine, RiskGuardianV1

paper = PaperTradingEngine()
guarded = GuardedPaperTradingEngine(paper, RiskGuardianV1())
```

---

## Auditoria

`guardian.get_audit_log()` — histórico de `reason`, `blocked`, PnL e cooldown por avaliação.

---

**RISK GUARDIAN V1 OK**
