# Model Registry — v1 (Stage 14)

**Pacote:** `microstructure/model_registry/`  
**Testes:** `tests/test_model_registry_v1.py`

> Distinto de `microstructure/model/` (treino v1). Este pacote **registra** modelos já treinados e suas métricas.

---

## Papel no pipeline

```
… → REPORTING → ARTIFACTS → EXPERIMENTS → MODEL REGISTRY
```

Centraliza modelos treinados para comparação e seleção do melhor por métrica (ex.: `sharpe`).

---

## API

```python
from microstructure.model_registry import (
    register_model,
    save_registry,
    load_registry,
    get_best_model,
    list_models,
)

entry = register_model(
    model_name="wdo_logistic_v1",
    model_type="LogisticRegression",
    parameters={"horizon": 5, "train_size": 0.7, "ml_threshold": 0.55},
    metrics=report,  # generate_performance_report(bt)
)

save_registry("outputs/run_001")
load_registry("outputs/run_001")
best = get_best_model(metric="sharpe")
all_models = list_models()
```

---

## Estrutura de cada modelo

```json
{
    "model_id": "uuid",
    "timestamp": "2026-05-29T15:00:00Z",
    "model_name": "wdo_logistic_v1",
    "model_type": "LogisticRegression",
    "parameters": { "horizon": 5 },
    "metrics": { "sharpe": 1.2, "total_return": 0.03 }
}
```

Persistência: `{output_dir}/model_registry.json` com `{"version": 1, "models": [...]}`.

---

## Compatibilidade

| Módulo | Uso |
|--------|-----|
| **Reporting v1** | `metrics` = saída de `generate_performance_report` |
| **Artifacts v1** | Mesmo `output_dir`; arquivo `model_registry.json` separado |
| **Experiments v1** | `{experiment_id}.json` no mesmo diretório; `list_experiments` não lê o registry |

---

## `get_best_model`

- Argumento `metric` (default `"sharpe"`): maior valor vence
- Métrica ausente ou inválida → tratada como `-inf`
- Registro vazio → `ValueError`

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_model_registry_v1.py -v -s
```

Saída esperada: `MODEL REGISTRY V1 OK`

---

## Roadmap (v2+)

- Referência ao objeto sklearn serializado (joblib)
- Vínculo `experiment_id` ↔ `model_id`
- Promoção de modelo “production”
- CLI `list` / `promote`
