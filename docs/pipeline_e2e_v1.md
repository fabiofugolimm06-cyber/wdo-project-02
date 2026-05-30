# End-to-End Pipeline — v1 (Stage 10)

**Pacote:** `microstructure/pipeline/`  
**Função:** `run_full_pipeline(df, price_col="fechamento")`  
**Testes:** `tests/test_pipeline_e2e_v1.py`

---

## Papel

Orquestra todos os estágios já validados em **uma única chamada**, sem modificar os módulos internos.

```
DATA
  → FEATURES      build_dataset
  → LABELS        create_horizon_labels + drop_invalid_label_rows
  → CLEAN         drop_nan_feature_rows
  → MODEL         split → train → predict → generate_ml_signal
  → EXECUTION     simulate_execution (hold-out)
  → BACKTEST      run_backtest_v3 (hold-out)
```

---

## Uso

```python
from microstructure.pipeline import run_full_pipeline

result = run_full_pipeline(df, price_col="fechamento")

print(result["features_shape"])
print(result["model_metrics"])
print(result["execution_metrics"])
print(result["backtest_metrics"])
```

### Parâmetros opcionais

| Parâmetro | Default | Descrição |
|-----------|---------|-----------|
| `horizon` | `5` | Labels horizon |
| `train_size` | `0.70` | Split temporal treino |
| `ml_threshold` | `0.55` | Limiar `generate_ml_signal` |
| `initial_capital` | `100_000` | Execução simulada |
| `position_size` | `1.0` | Tamanho de posição |

---

## Retorno

```python
{
    "features_shape": (n_rows, n_features),
    "model_metrics": {
        "accuracy", "precision", "recall", "f1"
    },
    "execution_metrics": {
        "num_orders", "long_entries", "short_entries", "flat_periods"
    },
    "backtest_metrics": {
        "total_return", "sharpe", "max_drawdown", ...
    },
}
```

**Hold-out:** execução e backtest usam apenas o conjunto de **teste** do split temporal (sinais ML OOS).

---

## O que não faz (v1)

- Não chama `generate_signals` (sinais rule-based); sinais = ML no teste
- Não altera `run_wdo_pipeline` em `run_pipeline.py` (pipeline legado FEATURES→SIGNALS→BACKTEST v1)
- Não substitui walk-forward / purged k-fold (rodar separadamente)

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_pipeline_e2e_v1.py -v -s
```

Saída esperada: `PIPELINE E2E V1 OK`

---

## Módulos tocados (somente orquestração)

| Estágio | Import |
|---------|--------|
| Features | `build_dataset` |
| Labels | `create_horizon_labels`, `drop_invalid_label_rows` |
| Model | `drop_nan_feature_rows`, split, train, predict, ML signal, metrics |
| Execution | `simulate_execution` |
| Backtest | `run_backtest_v3` |
