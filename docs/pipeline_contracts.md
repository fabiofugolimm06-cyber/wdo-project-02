# Contratos de pipeline — WDO PROJECT 02

**Contract-Based Pipeline System** — versionamento, diff e CI gate.

| Artefato | ID |
|----------|-----|
| ML pipeline | `ml_pipeline_contract_v1` (`1.0.0`) |
| E2E pipeline | `full_pipeline_contract_v1` (`1.0.0`) |

**Registry (fonte única):** `microstructure/contracts/registry.py`  
`get_contract("ml_pipeline:v1")` · `contract_registry.list_contracts()`  

Definições v1: `microstructure/contracts/versions.py` (registradas em `CONTRACTS`)  
Enforcement: `validate_ml_contract()` / `validate_full_pipeline_contract()` em `enforcement.py`  
Baselines CI: `microstructure/contracts/baselines/*.json`  
Snapshots: `tests/snapshots/ml_pipeline_v1_seed42.json`, `full_pipeline_v1_seed42.json`  
Diff: `diff_contracts(baseline, current)` → `breaking_changes`  
Compat: `validate_compatibility(old_contract, output)`

Schemas legados: `microstructure/contracts/pipeline_schemas.py`

## `run_ml_pipeline_v1` (ML only)

**Módulo:** `microstructure/model/pipeline.py`

**Top-level keys:**

| Chave | Tipo |
|-------|------|
| `n_ml` | int |
| `n_train` | int |
| `n_test` | int |
| `metrics` | dict |
| `signals` | ndarray |
| `proba` | ndarray |

**`metrics` — somente classificação (sklearn):**

- `accuracy`
- `precision`
- `recall`
- `f1`

**Proibido em `metrics`:** `sharpe`, `total_return`, `max_drawdown`, `pnl`, etc.

**Isolamento:** não importa `microstructure.backtest` nem `execution`.

---

## `run_full_pipeline` (E2E)

**Módulo:** `microstructure/pipeline/end_to_end.py`

**Top-level keys:**

| Chave | Conteúdo |
|-------|----------|
| `features_shape` | tuple |
| `model_metrics` | mesmo contrato ML acima |
| `execution_metrics` | `num_orders`, `long_entries`, `short_entries`, `flat_periods` |
| `backtest_metrics` | inclui `sharpe`, `total_return`, `max_drawdown`, `win_rate`, `completed_trades`, … |

**`sharpe` existe apenas em `backtest_metrics`, nunca em `model_metrics`.**

---

## Validação automática

```python
from microstructure.contracts import (
    validate_ml_pipeline_result,
    validate_e2e_pipeline_result,
    ML_METRIC_KEYS,
)
```

Chamadas em runtime nos pipelines + testes em `tests/test_pipeline_contracts.py`.
