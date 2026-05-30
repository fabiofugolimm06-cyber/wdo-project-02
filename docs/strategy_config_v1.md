# Strategy Config System — v1 (Stage 15)

**Pacote:** `microstructure/strategy_config/`  
**Testes:** `tests/test_strategy_config_v1.py`

---

## Objetivo

Centralizar parâmetros operacionais do pipeline em um **JSON versionado**, sem alterar módulos existentes.

---

## API

```python
from microstructure.strategy_config import (
    get_default_config,
    create_strategy_config,
    validate_strategy_config,
    save_strategy_config,
    load_strategy_config,
    flatten_parameters,
)

cfg = get_default_config("wdo_default")
cfg = create_strategy_config("wdo_v2", overrides={"labeling": {"horizon": 10}})

save_strategy_config("outputs/run_001", cfg)
loaded = load_strategy_config("outputs/run_001")
flat = flatten_parameters(loaded)  # experiments / model_registry
```

---

## Estrutura

```json
{
    "config_id": "uuid",
    "timestamp": "2026-05-29T16:00:00Z",
    "config_version": "1",
    "strategy_name": "wdo_default",
    "parameters": {
        "data": { "price_col": "fechamento" },
        "labeling": { "horizon": 5 },
        "model": { "train_size": 0.70, "ml_threshold": 0.55 },
        "backtest": {
            "max_hold_bars": 5,
            "stop_loss": 0.01,
            "take_profit": 0.02,
            "cost_per_trade": 0.0001,
            "slippage": 0.00005
        },
        "execution": {
            "initial_capital": 100000.0,
            "position_size": 1.0
        },
        "validation": {
            "walk_forward": { "train_size": 0.70, "step_size": 20 },
            "purged_kfold": { "n_splits": 5, "horizon": 5, "embargo": 1 }
        }
    }
}
```

Arquivo padrão: `{run_dir}/strategy_config.json`

---

## Compatibilidade

| Módulo | Integração |
|--------|------------|
| **Pipeline E2E** | Defaults espelham `run_full_pipeline` + backtest v3 |
| **Experiments v1** | `flatten_parameters(cfg)` → `parameters` do experimento |
| **Model Registry v1** | Mesmo `parameters` achatado no registro |
| **Artifacts v1** | Mesmo `output_dir`; arquivo distinto |

---

## Seções `parameters`

| Seção | Uso |
|-------|-----|
| `data` | OHLCV / `price_col` |
| `labeling` | `create_horizon_labels` |
| `model` | split, treino, `generate_ml_signal` |
| `backtest` | `run_backtest_v3` |
| `execution` | `simulate_execution` |
| `validation` | walk-forward / purged k-fold |

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_strategy_config_v1.py -v -s
```

Saída esperada: `STRATEGY CONFIG V1 OK`

---

## Roadmap (v2+)

- `apply_config_to_pipeline(cfg, df)` (orquestrador opcional)
- Schema JSON formal / migração `config_version`
- Perfis `dev` / `prod` / `research`
- Validação cruzada de ranges por instrumento (WDO)
