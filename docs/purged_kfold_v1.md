# Purged K-Fold Validation — v1 (Stage 08)

**Módulo:** `microstructure/model/purged_kfold.py`  
**Testes:** `tests/test_purged_kfold_v1.py`

---

## Papel no pipeline

```
FEATURES → LABELS → (limpeza) → purged_kfold_validation → métricas OOS
```

**Não altera:** features, labeling, signals, backtest, nem módulos Model v1 / walk-forward (apenas reutiliza trainer e metrics).

---

## API

```python
from microstructure.model import purged_kfold_validation, drop_nan_feature_rows
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.features.datasets import build_dataset

X = build_dataset(df)
y = create_horizon_labels(df, price_col="fechamento", horizon=5)
X_ml, y_ml = drop_invalid_label_rows(X, y)
X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)

result = purged_kfold_validation(
    X_ml,
    y_ml,
    n_splits=5,
    horizon=5,
    embargo=1,
)
```

### Retorno

```python
{
    "fold_metrics": [{"accuracy", "precision", "recall", "f1"}, ...],
    "avg_accuracy": ...,
    "avg_precision": ...,
    "avg_recall": ...,
    "avg_f1": ...,
    "num_folds": ...,
}
```

---

## Lógica

| Etapa | Regra |
|-------|--------|
| Teste | `n_splits` blocos contíguos ao longo do tempo (sem shuffle) |
| Purge | Remove do treino índices `i` com label em `[i, i+horizon)` sobreposto ao teste |
| Embargo | Remove do treino barras `[test_end, test_end + embargo)` |
| Treino | Restante (pode incluir barras antes **e** depois do teste) |

Função auxiliar: `generate_purged_kfold_splits(n_samples, n_splits, horizon, embargo)`.

Cada fold: `train_logistic_model` → `evaluate_classifier`.

---

## Anti-leakage

- Sem shuffle
- Purge alinhado ao **horizon label** (mesmo `horizon` de `create_horizon_labels`)
- Embargo reduz correlação serial entre treino e teste

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_purged_kfold_v1.py -v -s
```

Saída esperada: `PURGED KFOLD V1 OK`

---

## Roadmap (v2+)

- Timestamps por fold
- Purge por intervalo de eventos (triple barrier)
- Combinação com walk-forward
