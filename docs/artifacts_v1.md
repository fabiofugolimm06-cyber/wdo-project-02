# Artifact Persistence — v1 (Stage 12)

**Pacote:** `microstructure/artifacts/`  
**Função:** `save_pipeline_artifacts(output_dir, pipeline_result)`  
**Testes:** `tests/test_artifacts_v1.py`

---

## Papel no pipeline

```
… → REPORTING → ARTIFACTS (JSON em disco)
```

Persiste métricas para **auditoria** e **reprodutibilidade**, sem alterar módulos anteriores.

---

## Uso

```python
from microstructure.pipeline import run_full_pipeline
from microstructure.reporting import generate_performance_report
from microstructure.artifacts import save_pipeline_artifacts

pipeline = run_full_pipeline(df, price_col="fechamento")
# report_metrics: gerar via generate_performance_report(bt) se necessário

save_info = save_pipeline_artifacts(
    "outputs/run_001",
    {
        "model_metrics": pipeline["model_metrics"],
        "execution_metrics": pipeline["execution_metrics"],
        "backtest_metrics": pipeline["backtest_metrics"],
        "report_metrics": report,  # dict de generate_performance_report
    },
)
print(save_info["files_saved"])
```

---

## Arquivos gerados

| Arquivo | Chave em `pipeline_result` |
|---------|---------------------------|
| `model_metrics.json` | `model_metrics` |
| `execution_metrics.json` | `execution_metrics` |
| `backtest_metrics.json` | `backtest_metrics` |
| `report_metrics.json` | `report_metrics` |

- Diretório criado automaticamente (`mkdir -p`)
- Arquivos existentes são **sobrescritos**
- JSON indentado, UTF-8
- `inf` / `-inf` em floats → string `"inf"` / `"-inf"` (JSON válido)

---

## Retorno

```python
{"files_saved": ["/abs/path/model_metrics.json", ...]}
```

---

## Validação

| Erro | Condição |
|------|----------|
| `ValueError` | `output_dir` vazio ou aponta para arquivo |
| `TypeError` | `pipeline_result` ou `output_dir` tipo inválido |
| `ValueError` | métrica presente mas não é `dict` |

Chaves ausentes em `pipeline_result` → arquivo com `{}`.

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_artifacts_v1.py -v -s
```

Saída esperada: `ARTIFACTS V1 OK`

---

## Roadmap (v2+)

- Timestamp / run_id no path
- Salvar `features_shape` e metadados (`pipeline_meta.json`)
- Parquet para séries (`df` backtest)
- Hash / manifest de reprodutibilidade
