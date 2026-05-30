# Hyperparameter Optimization — Grid Search v1 (Stage 18)

**Pacote:** `microstructure/optimization/`  
**Testes:** `tests/test_grid_search_v1.py`

---

## Papel no pipeline

```
LABELS → MODEL → GRID SEARCH → VALIDATION → MODEL REGISTRY
```

Busca sistemática de hiperparâmetros com **split temporal** (sem shuffle), reutilizando Model v1.

---

## API

```python
from microstructure.optimization import run_grid_search

result = run_grid_search(
    X_ml,
    y_ml,
    param_grid={
        "C": [0.1, 1.0, 10.0],
        "train_size": [0.65, 0.75],
    },
    scoring="f1",
)
```

### Retorno

```python
{
    "best_params": {"C": 1.0, "train_size": 0.75},
    "best_score": 0.42,
    "best_metrics": {"accuracy", "precision", "recall", "f1"},
    "all_results": [
        {"params": {...}, "score": 0.40, "metrics": {...}},
        ...
    ],
}
```

---

## Parâmetros suportados

| Chave | Tipo | Uso |
|-------|------|-----|
| `train_size` | split | `train_test_split_time_series` |
| `C` | modelo | `LogisticRegression` |
| `penalty` | modelo | idem |
| `class_weight` | modelo | idem |
| `solver` | modelo | idem |
| `max_iter` | modelo | idem |

- Sem chaves de modelo → `train_logistic_model()` (baseline)
- Com chaves de modelo → treino equivalente ao trainer (validação + `drop_nan_feature_rows`)

**Scoring:** `accuracy`, `precision`, `recall`, `f1` (default `f1`).

---

## Anti-leakage

- Sem `shuffle`
- Treino sempre antes do teste (`train_test_split_time_series`)
- Mesmo `X`, `y` já limpos (`drop_invalid_label_rows`, `drop_nan_feature_rows`)

---

## Integração Model Registry

```python
from microstructure.model_registry import register_model, save_registry

register_model(
    "grid_wdo_v1",
    "LogisticRegression",
    result["best_params"],
    result["best_metrics"],
)
save_registry(run_directory)
```

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_grid_search_v1.py -v -s
```

Saída esperada: `GRID SEARCH V1 OK`

---

## Roadmap (v2+)

- Random search / Bayesian
- Walk-forward como scoring externo
- Purged K-Fold no loop
- `ml_threshold` em grid pós-`predict_proba`
