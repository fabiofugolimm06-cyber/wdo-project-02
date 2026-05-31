# WDO PROJECT 02 — Prompt de transição de contexto

> Colar este ficheiro (`@docs/CHAT_TRANSITION_WDO_PROJECT_02.md`) ou o bloco abaixo no primeiro mensagem de um chat novo.

---

## CONTEXTO DO SISTEMA

Estou a construir o **WDO PROJECT 02** (`C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02`): research quantitativo WDO (mini dólar) com ML + backtest + execução simulada, arquitetura **contract-driven** (mindset protobuf).

Não é só ML — pipeline completa com separação rígida:

| Camada | Papel |
|--------|-------|
| ML Research | `run_ml_pipeline_v1` — só métricas sklearn |
| E2E | `run_full_pipeline` — ML + execution + backtest |
| Contratos | schema, forbidden keys, versionamento |
| Enforcement | validação imediata em runtime |
| CI | contratos, diff, snapshot, determinismo 20× |

**Bot em produção (outro repo):** V6-Follow-Trending — visual/pixels no Profit. Este projeto é research; não confundir com Cerebro-Claude (legado).

**Regra de ouro:** ML nunca contém sharpe/pnl/drawdown/execution. Isso só existe no E2E em `backtest_metrics`.

---

## ARQUITETURA JÁ IMPLEMENTADA

### 1. ML Pipeline — `microstructure/model/pipeline.py`

`run_ml_pipeline_v1(df, seed=42)` retorna:

- `n_ml`, `n_train`, `n_test`, `metrics{accuracy,precision,recall,f1}`, `signals`, `proba`

**Proibido:** sharpe, pnl, drawdown, backtest_metrics, execution_metrics.

Validação: `validate_ml_contract(output)` em `contracts/enforcement.py`.

### 2. E2E Pipeline — `microstructure/pipeline/end_to_end.py`

`run_full_pipeline(df)` retorna:

- `features_shape`, `model_metrics`, `execution_metrics`, `backtest_metrics` (inclui sharpe)

Validação: `validate_full_pipeline_contract(output)`.

### 3. Contract System (CORE)

| Contrato | ID | Versão |
|----------|-----|--------|
| ML | `ml_pipeline_contract_v1` | 1.0.0 |
| E2E | `full_pipeline_contract_v1` | 1.0.0 |

**Ficheiros:**

- `microstructure/contracts/versions.py` — definições
- `microstructure/contracts/contract_models.py` — PipelineContract, NestedOutputSchema
- `microstructure/contracts/registry.py` — **fonte única de verdade**
- `microstructure/contracts/enforcement.py` — engine de validação
- `microstructure/contracts/compatibility.py` — `validate_compatibility(old_contract, output)`
- `microstructure/contracts/schema_diff.py` — `diff_contracts(v_old, v_new)`
- `microstructure/contracts/snapshot.py` — build/compare snapshots
- `microstructure/contracts/pipeline_schemas.py` — API legada + constantes
- `microstructure/contracts/baselines/*.json` — baseline CI

**Registry (usar sempre):**

```python
from microstructure.contracts import get_contract, contract_registry

get_contract("ml_pipeline:v1")      # ou "ml_pipeline" ou "ml_pipeline_contract_v1"
contract_registry.list_contracts()  # ("full_pipeline:v1", "ml_pipeline:v1")
contract_registry.get_active_version("ml_pipeline")  # "v1"
```

`CONTRACTS = {"ml_pipeline:v1": ..., "full_pipeline:v1": ...}` — registry frozen após bootstrap; sem duplicação/overwrite.

### 4. Versionamento

Breaking change → novo v2, **nunca** alterar v1 in-place.

CI: `tests/test_contract_diff_ci.py` compara código vs `baselines/*.json`; `breaking_changes == True` → FAIL.

### 5. Schema diff

`diff_contracts(old, new)` → `added_keys`, `removed_keys`, `modified_constraints`, `breaking_changes`.

**Breaking:** remoção de keys, relaxação de `forbidden_keys`, `allow_extra: True→False`.

### 6. Snapshots

| Ficheiro | Pipeline |
|----------|----------|
| `tests/snapshots/ml_pipeline_v1_seed42.json` | ML, 200 barras, seed 42 |
| `tests/snapshots/full_pipeline_v1_seed42.json` | E2E, 300 barras, seed 42 |

Regras: schema/structure = igualdade estrita; números com `epsilon=1e-9`.

Testes: `tests/test_pipeline_snapshot_v1.py`.

### 7. Determinismo global

- `microstructure/determinism.py` — `set_global_determinism(seed=42)`, `WDO_PROJECT_RANDOM_SEED`
- Env: `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `PYTHONPATH=.`
- `tests/conftest.py` — seed por teste
- Fix importante: `volume_zscore` com `min_periods=1`; `drop_nan_feature_rows` só filtra `y.notna()`
- `tests/test_ci_stress_reliability.py` — 20× `run_ml_pipeline_v1` + fingerprint estável

### 8. CI como engine

`.github/workflows/ci.yml` — pytest completo + stress determinismo.

**Testes de contrato/guardrail:**

- `test_pipeline_contracts.py` — ML vs E2E, isolamento AST (ML não importa backtest)
- `test_contract_enforcement.py`
- `test_contract_registry.py`
- `test_contract_schema_diff.py`
- `test_contract_diff_ci.py`
- `test_pipeline_regression.py` — fingerprint ML, sem sharpe

**Estado (última verificação):** 260 testes verdes (Windows Python 3.14).

---

## ESTRUTURA DE PASTAS RELEVANTE

```
microstructure/
  contracts/     ← registry, enforcement, diff, snapshot
  model/         ← pipeline.py, trainer, metrics
  pipeline/      ← end_to_end.py
  backtest/      ← engine_v3 (sem sklearn)
  execution/
  features/
  labeling/
  determinism.py
tests/
  snapshots/
  ohlcv_data.py  ← make_ohlcv(n, seed=42)
docs/pipeline_contracts.md
```

---

## HISTÓRICO DA SESSÃO ANTERIOR

- Formalização ML vs E2E (métricas separadas).
- Guardrails + `pipeline_schemas` + validação runtime nos pipelines.
- Contract models + versions v1 + schema diff + compatibility.
- Snapshots ML + E2E + testes CI diff.
- Enforcement engine (`validate_ml_contract`, `validate_full_pipeline_contract`).
- **Contract Registry central** (`registry.py`) — ponto único de verdade.
- Determinismo estabilizado (`volume_zscore`, `drop_nan`, seeds, stress 20×).
- Correções de testes que misturavam sharpe no ML pipeline.

**Não alterámos:** lógica interna do backtest engine, treino sklearn além de seeds/solver, bot V6.

---

## O QUE FALTA / PRÓXIMO NÍVEL (“DIAMANTE”)

Prioridade sugerida:

1. **Data Contract** — fingerprint/version hash do OHLCV; manifest dataset nos snapshots.
2. **Trading Decision Contract** — schema formal sinal → decisão → execução.
3. **Strict Research/Prod separation** — doc + lint/import guard V6 ↔ WDO PROJECT.
4. **Snapshot como spec** — gerar spec a partir de snapshot (opcional).
5. **Evolution rule engine** — migração explícita v1→v2 (não só diff).
6. **Journal operacional** — `HISTORICO_OPERACIONAL.md` estilo V6 neste repo.
7. **Snapshot E2E menos frágil** — fixar só required + schema keys estáveis (extras em backtest quebram CI se engine adicionar métricas).
8. **Walk-forward gate em CI** (opcional, não bloqueante no início).
9. **CI em camadas** — job rápido (contratos) vs lento (E2E full).
10. **`ml_pipeline_contract_v2`** — só quando houver mudança real; atualizar baselines.

---

## INSTRUÇÕES PARA O ASSISTENTE

1. Ler `docs/pipeline_contracts.md` e `microstructure/contracts/registry.py` antes de mudar contratos.
2. Não simplificar arquitetura contract-driven.
3. Não quebrar contratos v1; evoluir via v2 + registry + baseline novo.
4. Não misturar métricas ML e backtest.
5. Preservar determinismo (`set_global_determinism`, threads=1).
6. Mudanças em pipeline output → atualizar snapshot ou bump de versão com diff explícito.
7. Preferir `get_contract()` em vez de import direto de `versions.py` em código novo.
8. Correr testes: `PYTHONPATH=. python -m pytest tests/ -q`
9. Não commitar sem pedido explícito do utilizador.

---

## COMANDOS ÚTEIS

```powershell
cd "C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02"
$env:PYTHONPATH="."
$env:OMP_NUM_THREADS="1"
python -m pytest tests/ -q
python -m pytest tests/test_contract_registry.py tests/test_contract_diff_ci.py -v
```

---

## REFERÊNCIA RÁPIDA — IMPORTS

```python
from microstructure.contracts import (
    get_contract,
    contract_registry,
    validate_ml_contract,
    validate_full_pipeline_contract,
    validate_compatibility,
    diff_contracts,
)
from microstructure.model.pipeline import run_ml_pipeline_v1, pipeline_fingerprint
from microstructure.pipeline.end_to_end import run_full_pipeline
from microstructure.determinism import set_global_determinism, WDO_PROJECT_RANDOM_SEED
from tests.ohlcv_data import make_ohlcv
```

---

## OBJETIVO FINAL

Sistema com:

- determinismo absoluto
- contratos versionados
- evolução controlada (protobuf mindset)
- CI como guardião de arquitetura
- zero regressão silenciosa
- separação rígida entre ML e trading real
