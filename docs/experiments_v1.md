# Experiment Tracking — v1 (Stage 13)

**Pacote:** `microstructure/experiments/`  
**Testes:** `tests/test_experiments_v1.py`

---

## Papel no pipeline

```
… → REPORTING → ARTIFACTS → EXPERIMENT TRACKING
```

Registra **nome**, **parâmetros** e **métricas** de cada run para comparação e auditoria, sem alterar módulos anteriores.

---

## API

```python
from microstructure.experiments import (
    create_experiment,
    save_experiment,
    load_experiment,
    list_experiments,
)

exp = create_experiment(
    experiment_name="wdo_horizon5",
    parameters={"horizon": 5, "train_size": 0.7},
    metrics=report,  # ex.: generate_performance_report(bt)
)

save_experiment("outputs/run_001", exp)
loaded = load_experiment("outputs/run_001/<uuid>.json")
runs = list_experiments("outputs/run_001")
```

---

## Estrutura JSON

```json
{
    "experiment_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-05-29T14:30:00Z",
    "experiment_name": "wdo_horizon5",
    "parameters": { "horizon": 5, "train_size": 0.7 },
    "metrics": { "total_return": 0.02, "sharpe": 0.8 }
}
```

| Campo | Origem |
|-------|--------|
| `experiment_id` | UUID4 automático |
| `timestamp` | UTC ISO8601 automático |
| `experiment_name` | argumento |
| `parameters` | hiperparâmetros / config |
| `metrics` | reporting, model, backtest, etc. |

Arquivo salvo: `{output_dir}/{experiment_id}.json`

---

## Compatibilidade ARTIFACTS V1

No mesmo `output_dir` de uma run:

```
run_001/
├── model_metrics.json          ← artifacts
├── execution_metrics.json
├── backtest_metrics.json
├── report_metrics.json
└── <experiment_id>.json        ← experiment tracking
```

`list_experiments()` ignora os quatro `*_metrics.json` e lista só experimentos válidos.

---

## Fluxo recomendado

```python
from microstructure.pipeline import run_full_pipeline
from microstructure.reporting import generate_performance_report
from microstructure.artifacts import save_pipeline_artifacts
from microstructure.experiments import create_experiment, save_experiment

pipeline = run_full_pipeline(df)
# report + bt completo conforme necessário

save_pipeline_artifacts(run_dir, {
    "model_metrics": pipeline["model_metrics"],
    "execution_metrics": pipeline["execution_metrics"],
    "backtest_metrics": pipeline["backtest_metrics"],
    "report_metrics": report,
})

exp = create_experiment("run_001", parameters={...}, metrics=report)
save_experiment(run_dir, exp)
```

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_experiments_v1.py -v -s
```

Saída esperada: `EXPERIMENT TRACKING V1 OK`

---

## Roadmap (v2+)

- Índice `experiments_index.json`
- Comparação tabular entre runs
- Tags / git commit / hash de dados
- SQLite ou MLflow opcional
