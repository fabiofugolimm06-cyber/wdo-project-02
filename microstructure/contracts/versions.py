"""
microstructure/contracts/versions.py — definições versionadas de contratos v1.
"""

from __future__ import annotations

from microstructure.contracts.contract_models import NestedOutputSchema, PipelineContract

_ML_METRIC_KEYS = frozenset({"accuracy", "precision", "recall", "f1"})

_FORBIDDEN_IN_ML_METRICS = frozenset({
    "sharpe",
    "sharpe_ratio",
    "total_return",
    "max_drawdown",
    "win_rate",
    "total_pnl",
    "pnl",
    "profit_factor",
    "num_trades",
    "completed_trades",
})

_ML_TOP_KEYS = frozenset({
    "n_ml",
    "n_train",
    "n_test",
    "metrics",
    "signals",
    "proba",
})

_E2E_TOP_KEYS = frozenset({
    "features_shape",
    "model_metrics",
    "execution_metrics",
    "backtest_metrics",
})

_E2E_EXEC_REQUIRED = frozenset({
    "num_orders",
    "long_entries",
    "short_entries",
    "flat_periods",
})

_E2E_BACKTEST_REQUIRED = frozenset({
    "sharpe",
    "total_return",
    "max_drawdown",
    "win_rate",
    "completed_trades",
})

ml_pipeline_contract_v1 = PipelineContract(
    contract_id="ml_pipeline_contract_v1",
    version="1.0.0",
    output_schema={
        "n_ml": "int — linhas após limpeza de labels/features",
        "n_train": "int — linhas de treino (split temporal)",
        "n_test": "int — linhas de teste",
        "metrics": "dict — classificação sklearn (4 chaves fixas)",
        "signals": "ndarray[int] — sinais discretos no hold-out",
        "proba": "ndarray[float] — probabilidades no hold-out",
    },
    required_top_keys=_ML_TOP_KEYS,
    forbidden_top_keys=frozenset({
        "backtest_metrics",
        "execution_metrics",
        "model_metrics",
        "features_shape",
    }),
    nested_schemas=(
        NestedOutputSchema(
            block_name="metrics",
            required_keys=_ML_METRIC_KEYS,
            forbidden_keys=_FORBIDDEN_IN_ML_METRICS,
            allow_extra_keys=False,
        ),
    ),
    allow_extra_top_keys=False,
)

full_pipeline_contract_v1 = PipelineContract(
    contract_id="full_pipeline_contract_v1",
    version="1.0.0",
    output_schema={
        "features_shape": "tuple — shape (n_rows, n_features) pós-limpeza",
        "model_metrics": "dict — mesmo contrato ML (4 métricas)",
        "execution_metrics": "dict — métricas de simulação de execução",
        "backtest_metrics": "dict — métricas de backtest (inclui sharpe)",
    },
    required_top_keys=_E2E_TOP_KEYS,
    forbidden_top_keys=frozenset(),
    nested_schemas=(
        NestedOutputSchema(
            block_name="model_metrics",
            required_keys=_ML_METRIC_KEYS,
            forbidden_keys=_FORBIDDEN_IN_ML_METRICS,
            allow_extra_keys=False,
        ),
        NestedOutputSchema(
            block_name="execution_metrics",
            required_keys=_E2E_EXEC_REQUIRED,
            forbidden_keys=frozenset(),
            allow_extra_keys=True,
        ),
        NestedOutputSchema(
            block_name="backtest_metrics",
            required_keys=_E2E_BACKTEST_REQUIRED,
            forbidden_keys=frozenset(),
            allow_extra_keys=True,
        ),
    ),
    allow_extra_top_keys=False,
)
