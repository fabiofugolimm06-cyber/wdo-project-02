# Decision Engine v1 — Decision Core Unification

**Módulo:** `microstructure/core/decision_engine.py`  
**Função:** `run_decision_pipeline()`  
**Testes:** `tests/test_decision_engine_v1.py`

---

## Papel

**Cérebro final do sistema** — uma entrada unifica research e execução:

```
DATA → FEATURES → [LABELS treino] → SINAIS → RISK → (Backtest / Execution Bridge)
```

Não substitui módulos existentes; apenas **orquestra** imports já validados.

---

## API

```python
from microstructure.core import run_decision_pipeline

result = run_decision_pipeline(
    df,
    mode="signal_only",   # "signal_only" | "ml" | "hybrid"
    model=None,           # LogisticRegression pré-treinado (ml/hybrid)
    threshold=0.55,
    apply_risk=True,
    allow_trading=True,
)

signals = result["signals"]
X = result["features"]
```

### Retorno

```python
{
    "signals": pd.Series,       # {-1, 0, 1}
    "features": pd.DataFrame,
    "mode": str,
    "model_used": bool,
    "timestamp_index": pd.DatetimeIndex,
}
```

---

## Modos

| Modo | Sinais |
|------|--------|
| `signal_only` | `generate_signals` (returns + delta) |
| `ml` | `predict_proba` + `generate_ml_signal` (0/1 mapeado na série) |
| `hybrid` | Rule + ML: compra se rule==1 e ML==1; venda se rule==-1 e ML==0 |

### Treino / labels (anti-leakage)

- Com **`model` fornecido**: inferência em todo `X` (features causais de `build_dataset`).
- Com **`model=None`** em `ml`/`hybrid`: labels só no **treino temporal** (`train_test_split_time_series`); predição apenas no **hold-out**; treino = sinal `0`.

---

## Risk layer

Opcional via `risk_filter` (`apply_risk=True`, `allow_trading`).

---

## Integrações

```python
# Backtest v3
from microstructure.backtest.engine_v3 import run_backtest_v3
sig = result["signals"].reindex(df.index).fillna(0)
run_backtest_v3(df, sig, price_col="fechamento")

# Execution Bridge
from microstructure.execution_bridge import ExecutionBridge
bridge = ExecutionBridge(mode="export")
for ts in result["signals"].index:
    bridge.process_signal(int(result["signals"][ts]), df.loc[ts, "fechamento"], ts)
```

---

## Garantias v1

- Determinístico (mesmo `df` + parâmetros → mesmos sinais)
- Sem shuffle
- Índice temporal monotônico obrigatório
- Compatível com backtest v3 e execution_bridge v1

---

## Testes

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_decision_engine_v1.py -v -s
```

Saída: `DECISION ENGINE V1 OK`

---

## Roadmap

- Plug-in Strategy Config explícito
- Risk com PnL live do paper
- Export direto para Run Manager + bridge JSON
