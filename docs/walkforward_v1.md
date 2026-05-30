# Walk-Forward Validation — v1

**Módulo:** `microstructure/model/walkforward.py`  
**Status:** Janela expansiva + Logistic Regression **v1 OK**

---

## Papel no pipeline

```
FEATURES → LABELS → (limpeza) → walk_forward_validation → métricas OOS
```

**Não altera:** `features/`, `labeling/`, `signal/`, `backtest/`, nem `split.py` / `trainer.py` / `metrics.py` (apenas reutiliza).

---

## API

```python
from microstructure.model import walk_forward_validation, drop_nan_feature_rows
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.features.datasets import build_dataset

X = build_dataset(df)
y = create_horizon_labels(df, price_col="fechamento", horizon=5)
X_ml, y_ml = drop_invalid_label_rows(X, y)
X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)

result = walk_forward_validation(
    X_ml,
    y_ml,
    train_size=0.70,
    step_size=20,
)
```

### Retorno

```python
{
    "fold_metrics": [
        {"accuracy": ..., "precision": ..., "recall": ..., "f1": ...},
        ...
    ],
    "avg_accuracy": ...,
    "avg_precision": ...,
    "avg_recall": ...,
    "avg_f1": ...,
    "num_folds": ...,
}
```

---

## Lógica (janela expansiva)

| Parâmetro | Significado |
|-----------|-------------|
| `train_size` | Primeiro treino usa barras `0 .. floor(n * train_size) - 1` |
| `step_size` | Cada fold testa as próximas `step_size` barras (último fold pode ser menor) |

```text
Fold 0: train [0, t0)     test [t0, t0 + step)
Fold 1: train [0, t1)     test [t1, t1 + step)   com t1 = t0 + len(test)
...
```

- **Sem shuffle**
- **Treino sempre antes do teste** no eixo temporal
- Treino **cresce** a cada fold (inclui OOS já observado no passado — padrão walk-forward research)

Cada fold chama:

1. `train_logistic_model(X_train, y_train)`
2. `evaluate_classifier(model, X_test, y_test)`

Médias `avg_*` = média aritmética entre folds.

---

## Anti-leakage

| Regra | Como |
|-------|------|
| Ordem temporal | Índice monotônico; sem `shuffle` |
| Teste OOS | Só barras **após** o fim do treino daquele fold |
| Labels | Usar `y` do Label Engine v1 (horizon); `drop_invalid_label_rows` |
| Features | Sem `shift(-k)` em X; `drop_nan_feature_rows` antes do WF |

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_walkforward_v1.py -v -s
```

---

## Roadmap (v2+)

- Janela rolante (tamanho fixo de treino)
- Embargo / purge entre treino e teste (López de Prado)
- Métricas por fold com timestamps (`train_end`, `test_end`)
- Integração opcional com backtest nos sinais ML
