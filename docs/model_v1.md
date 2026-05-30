# Model Engine — Stage 06 (Baseline ML)

**Pacote:** `microstructure/model/`  
**Status:** Split temporal + Logistic Regression **v1 OK**

---

## Papel no pipeline

```
DATA → FEATURES → SIGNALS → BACKTEST → LABELS → MODEL → EXECUTION
                                                    ↑
                                               você está aqui
```

**Não altera:** `features/`, `signal/`, `backtest/`, `labeling/`.

---

## Pipeline MODEL v1

```
FEATURES  →  build_dataset(df)           → X
LABELS    →  create_horizon_labels(df)  → y
            drop_invalid_label_rows(X, y) → X_ml, y_ml
CLEAN     →  drop_nan_feature_rows      → remove warmup NaN em X
SPLIT     →  train_test_split_time_series → treino / teste (temporal)
TRAIN     →  train_logistic_model        → model
PREDICT   →  predict_probabilities       → proba
            generate_ml_signal           → sinal {0, 1}
METRICS   →  evaluate_classifier         → accuracy, precision, recall, f1
```

---

## Uso completo

```python
from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.model import (
    drop_nan_feature_rows,
    train_test_split_time_series,
    train_logistic_model,
    predict_probabilities,
    generate_ml_signal,
    evaluate_classifier,
)

# 1. Features + labels (sem leakage em X)
X = build_dataset(df)
y = create_horizon_labels(df, price_col="fechamento", horizon=5)
X_ml, y_ml = drop_invalid_label_rows(X, y)
X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)

# 2. Split temporal (sem shuffle)
X_train, X_test, y_train, y_test = train_test_split_time_series(
    X_ml, y_ml, train_size=0.70
)

# 3. Treino
model = train_logistic_model(X_train, y_train)

# 4. Previsão
proba = predict_probabilities(model, X_test)
signals = generate_ml_signal(proba, threshold=0.55)

# 5. Métricas
metrics = evaluate_classifier(model, X_test, y_test)
```

---

## Módulos

| Arquivo | Função | Descrição |
|---------|--------|-----------|
| `split.py` | `train_test_split_time_series` | Primeiras `train_size`% = treino; resto = teste |
| `trainer.py` | `train_logistic_model` | `sklearn.linear_model.LogisticRegression` |
| `predict.py` | `predict_probabilities` | `model.predict_proba(X_test)` |
| `predict.py` | `generate_ml_signal` | `1` se P(classe 1) ≥ threshold (default 0.55) |
| `metrics.py` | `evaluate_classifier` | accuracy, precision, recall, f1 (binary) |
| `utils.py` | `drop_nan_feature_rows` | Remove barras com NaN em features (warmup) |

---

## Anti-leakage

| Regra | Implementação |
|-------|----------------|
| Split temporal | Sem `shuffle`; teste sempre **depois** do treino no tempo |
| Labels | `y[t]` só usa preço futuro (Stage 05); remover NaN com `drop_invalid_label_rows` |
| Features | `X[t]` não deve usar `shift(-k)`; manter contrato do Feature Engine |
| Sinais de trading | `generate_signals` é estágio separado; não misturar `signal` em `X` para ML sem intenção explícita |

---

## Dependência

- `scikit-learn` (`sklearn.linear_model.LogisticRegression`, métricas em `sklearn.metrics`)

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_model_v1.py -v -s
```

---

## Walk-forward (v1)

Ver `docs/walkforward_v1.md` e `walk_forward_validation()` em `microstructure/model/walkforward.py`.

## Roadmap (v2+)

- Purged K-Fold / embargo
- Modelos adicionais (RandomForest, calibração)
- Integração opcional: sinal ML → backtest v3 (sem alterar engines existentes)
- Feature selection e importância
