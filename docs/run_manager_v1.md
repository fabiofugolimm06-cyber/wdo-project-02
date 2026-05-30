# Run Management — v1 (Stage 16)

**Pacote:** `microstructure/run_manager/`  
**Testes:** `tests/test_run_manager_v1.py`

---

## Objetivo

Cada execução completa do pipeline ganha um **run_id** único, diretório padronizado e metadata persistida — base para artifacts, experiments e model registry.

---

## API

```python
from microstructure.strategy_config import get_default_config
from microstructure.run_manager import create_run, load_run_metadata

cfg = get_default_config("wdo_default")
run = create_run(cfg, base_dir="runs")

print(run["run_id"])           # run_20260529_143000
print(run["run_directory"])    # .../runs/run_20260529_143000
print(run["metadata_path"])
```

### Funções

| Função | Descrição |
|--------|-----------|
| `create_run(strategy_config, base_dir="runs")` | Diretório + `run_metadata.json` + `strategy_config.json` |
| `create_run_directory(base_dir, run_id=None)` | Só o diretório (sufixo `_001` se colidir) |
| `save_run_metadata(run_directory, metadata)` | Grava metadata |
| `load_run_metadata(run_directory)` | Carrega e valida |

---

## Layout de diretório

```
runs/
└── run_YYYYMMDD_HHMMSS/
    ├── run_metadata.json      ← Stage 16
    ├── strategy_config.json   ← Stage 15
    ├── model_metrics.json     ← Artifacts (após pipeline)
    ├── execution_metrics.json
    ├── backtest_metrics.json
    ├── report_metrics.json
    ├── model_registry.json    ← Model Registry
    └── <experiment_id>.json   ← Experiments
```

---

## `run_metadata.json`

```json
{
    "run_id": "run_20260529_143000",
    "timestamp": "2026-05-29T14:30:00Z",
    "config": { "...": "Strategy Config v1 completa" }
}
```

---

## Fluxo recomendado

```python
run = create_run(cfg, base_dir="runs")
run_dir = run["run_directory"]

# pipeline / reporting ...
save_pipeline_artifacts(run_dir, {...})
save_experiment(run_dir, create_experiment(...))
register_model(...); save_registry(run_dir)
```

---

## Compatibilidade

| Stage | Arquivo no `run_directory` |
|-------|---------------------------|
| 15 Strategy Config | `strategy_config.json` |
| 12 Artifacts | `*_metrics.json` |
| 13 Experiments | `{uuid}.json` |
| 14 Model Registry | `model_registry.json` |

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_run_manager_v1.py -v -s
```

Saída esperada: `RUN MANAGER V1 OK`

---

## Roadmap (v2+)

- `list_runs(base_dir)`
- Status da run (`created`, `completed`, `failed`)
- Symlink `runs/latest`
- Integração CLI única `python -m microstructure.run`
