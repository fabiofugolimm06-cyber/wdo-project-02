# Label Engine — Stage 05

**Pacote:** `microstructure/labeling/`  
**Status:** Horizon Labels **v1 OK** | Triple Barrier **roadmap (skeleton)**

---

## Papel no pipeline

```
DATA → FEATURES → SIGNALS → BACKTEST → LABELS → MODEL → EXECUTION
                                          ↑
                                     você está aqui
```

**Entrada:** `df` OHLCV (mesmo índice que `build_dataset`)  
**Saída:** `y` (Series) para parear com `X` na etapa MODEL

```python
from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows

X = build_dataset(df)
y = create_horizon_labels(df, horizon=5)
X_ml, y_ml = drop_invalid_label_rows(X, y)   # remove últimas 5 barras
```

---

## Horizon Labels (v1)

**Módulo:** `microstructure/labeling/horizon.py`

```python
y = create_horizon_labels(
    df,
    price_col="fechamento",
    horizon=5,
)
```

### Lógica

```text
future_return[t] = price[t + horizon] / price[t] - 1

y[t] = 1   se future_return[t] > 0
y[t] = 0   caso contrário (inclui zero)
```

### Propriedades

| Propriedade | Valor |
|-------------|--------|
| dtype | `Int8` (nullable) |
| valores válidos | `{0, 1}` |
| barras inválidas | últimas `horizon` → `NaN` |
| nome da Series | `label_horizon_{horizon}` |

### Exemplo

```python
idx = pd.date_range("2024-01-01", periods=200, freq="min")
df = pd.DataFrame({...}, index=idx)

y = create_horizon_labels(df, horizon=5)
# y.iloc[-5:] → NaN (sem preço futuro completo)
```

---

## Triple Barrier (roadmap)

**Módulo:** `microstructure/labeling/triple_barrier.py`

```python
from microstructure.labeling import create_triple_barrier_labels

# v1: levanta NotImplementedError (contrato definido)
create_triple_barrier_labels(
    df,
    price_col="fechamento",
    horizon=5,
    upper_barrier=0.02,   # +2% TP
    lower_barrier=0.01,   # -1% SL
    vertical_barrier=5,   # timeout
)
```

**Saída planeada (v2):** `{-1, 0, +1}` — qual barreira foi tocada primeiro.

Referência conceitual: López de Prado, *Advances in Financial Machine Learning* (2018).

---

## Anti-Leakage Rules

### Regras obrigatórias

1. **`df.index` deve ser `DatetimeIndex` monotônico** (igual ao Feature Engine).
2. **`y[t]` usa apenas `price[t]` e `price[t+horizon]`** — nunca preços antes de `t` para o label.
3. **`X[t]` não pode conter colunas derivadas de `y` ou de preços futuros** (`shift(-k)`, `future_*`, `target`, etc.).
4. **Treino ML:** usar `drop_invalid_label_rows(X, y)` para remover barras sem label.
5. **Nunca colocar `y` dentro de `build_dataset(df)`** — label é estágio separado.

### O que é permitido

| Em X (features) | Em y (labels) |
|-----------------|---------------|
| dados até barra `t` | retorno de `t` → `t+h` |
| rolling backward | `shift(-horizon)` no preço |

### O que é proibido

```python
# PROIBIDO em features
df["future_return"] = df["fechamento"].pct_change().shift(-5)
X["y"] = y
```

### Teste de não-vazamento (pytest)

`test_no_leakage_changing_future_price_does_not_affect_past_label` — alterar `fechamento[t+h]` não altera `y[t']` para `t' < t`.

---

## Utilitários

**`microstructure/labeling/utils.py`**

| Função | Uso |
|--------|-----|
| `validate_price_series(df)` | valida índice e coluna de preço |
| `drop_invalid_label_rows(X, y)` | dataset ML sem NaN em `y` |

---

## Imports

```python
from microstructure.labeling import (
    create_horizon_labels,
    create_triple_barrier_labels,
    drop_invalid_label_rows,
)
```

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_labeling_v1.py -v -s
```

---

## Próximo estágio: MODEL

Dataset supervisionado mínimo:

```python
X_ml, y_ml = drop_invalid_label_rows(
    build_dataset(df),
    create_horizon_labels(df, horizon=5),
)
# X_ml.shape → (n - horizon, n_features)
```

Walk-forward, PurgedKFold e embargo ficam na etapa MODEL (Stage 06).
