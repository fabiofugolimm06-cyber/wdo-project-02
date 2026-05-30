# CI/CD — WDO PROJECT 02

## GitHub Actions

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

**Dispara em:** `push` e `pull_request` nas branches `main`, `master`, `develop`.

### Etapas

1. `ubuntu-latest`, Python 3.12
2. `pip install -r requirements.txt`
3. `PYTHONPATH=.` + `PYTHONHASHSEED=42`
4. `pytest tests/` — suíte completa (~200 testes)
5. **Determinismo:** `test_ci_determinism_stress` (10 iterações + teste crítico)
   - `TestModelPipelineIntegration::test_full_pipeline`
   - `tests/test_project_determinism.py`

### Bloquear merge em falha

No GitHub: **Settings → Branches → Branch protection rule**

- Branch: `main` (ou `master`)
- ✅ Require status checks to pass before merging
- ✅ Selecionar o check: **pytest (ubuntu)** (job `test`)

Sem repositório remoto, use os scripts locais abaixo.

## CI local

```powershell
# Windows
.\scripts\run_ci.ps1
```

```bash
# Linux / macOS / Git Bash
chmod +x scripts/run_ci.sh
./scripts/run_ci.sh
```

## Dependências

- [`requirements.txt`](../requirements.txt) — CI + dev
- [`requirements_wdo.txt`](../requirements_wdo.txt) — pin mínimo legado

## Variáveis de ambiente

| Variável | Valor | Uso |
|----------|-------|-----|
| `PYTHONPATH` | `.` | imports `microstructure` |
| `PYTHONHASHSEED` | `42` | hash determinístico |
| `WDO_CI` | `1` | flag opcional em scripts |

## Teste crítico de determinismo

```bash
PYTHONPATH=. python -m pytest \
  tests/test_model_v1.py::TestModelPipelineIntegration::test_full_pipeline \
  tests/test_ci_determinism_stress.py -v
```

`test_ci_determinism_stress` executa o pipeline ML **10 vezes** e exige `n_ml == 195` e métricas idênticas.
