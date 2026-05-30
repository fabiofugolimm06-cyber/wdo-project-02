# Determinismo — WDO PROJECT 02

## Seed canônico

```python
from microstructure.determinism import (
    WDO_PROJECT_RANDOM_SEED,  # 42
    set_global_determinism,
)

set_global_determinism()  # np.random + random + PYTHONHASHSEED
```

## Testes

- `tests/conftest.py` — fixture `session` autouse fixa seeds em toda a suíte
- `tests/ohlcv_data.py` — `make_ohlcv(n, seed=42)` com `default_rng(seed)`

## Pipeline ML

| Etapa | Comportamento |
|-------|----------------|
| `build_dataset` | `df.copy()` |
| `create_horizon_labels` | `df.copy()` |
| `drop_invalid_label_rows` | `.copy()` |
| `drop_nan_feature_rows` | imputação causal (`ffill` + `0`), **sem drop** de linhas; `sort_index()` |
| `train_test_split_time_series` | split temporal, **sem shuffle** |
| `train_logistic_model` | `random_state=42` |

Linhas após horizon=5: `len(df) - horizon` (ex.: 200 → **195**).

## Scripts

Chame `set_global_determinism()` no início de `run_full_pipeline` e scripts locais.
