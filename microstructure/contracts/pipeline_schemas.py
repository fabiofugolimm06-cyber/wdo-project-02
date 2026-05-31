"""
microstructure/contracts/pipeline_schemas.py — API legada + delegação a contratos v1.
"""

from __future__ import annotations

from typing import Any, Mapping

from microstructure.contracts.enforcement import (
    validate_full_pipeline_contract,
    validate_ml_contract,
)
from microstructure.contracts.registry import (
    full_pipeline_contract_v1,
    get_contract,
    ml_pipeline_contract_v1,
)

# Re-export de constantes (compatibilidade com testes e imports existentes)
ML_METRIC_KEYS = frozenset(
    ml_pipeline_contract_v1.nested_schemas[0].required_keys
)

ML_PIPELINE_RESULT_TOP_KEYS = ml_pipeline_contract_v1.required_top_keys

FORBIDDEN_KEYS_IN_ML_METRICS = frozenset(
    ml_pipeline_contract_v1.nested_schemas[0].forbidden_keys
)

E2E_PIPELINE_TOP_KEYS = full_pipeline_contract_v1.required_top_keys

E2E_BACKTEST_METRIC_REQUIRED_KEYS = frozenset(
    full_pipeline_contract_v1.nested_schemas[2].required_keys
)

E2E_EXECUTION_METRIC_REQUIRED_KEYS = frozenset(
    full_pipeline_contract_v1.nested_schemas[1].required_keys
)


def validate_ml_metrics(metrics: Mapping[str, Any]) -> None:
    """Valida dict de métricas ML (regras de ``ml_pipeline_contract_v1``)."""
    if not isinstance(metrics, Mapping):
        raise ValueError("validate_ml_metrics: metrics deve ser mapping.")
    nested = get_contract("ml_pipeline:v1").nested_schemas[0]
    keys = frozenset(metrics.keys())
    forbidden = keys & nested.forbidden_keys
    if forbidden:
        raise ValueError(
            f"validate_ml_metrics: métricas de backtest em ML pipeline: {sorted(forbidden)}."
        )
    extra = keys - nested.required_keys
    if extra:
        raise ValueError(
            f"validate_ml_metrics: chaves não permitidas {sorted(extra)}. "
            f"Permitidas: {sorted(nested.required_keys)}."
        )
    missing = nested.required_keys - keys
    if missing:
        raise ValueError(
            f"validate_ml_metrics: chaves ausentes {sorted(missing)}."
        )
    for key in nested.required_keys:
        val = float(metrics[key])
        if val != val:
            raise ValueError(f"validate_ml_metrics: {key} é NaN.")


def validate_ml_pipeline_result(result: Mapping[str, Any]) -> None:
    """Valida retorno de ``run_ml_pipeline_v1`` (delega ao enforcement engine)."""
    validate_ml_contract(result)


def validate_e2e_pipeline_result(result: Mapping[str, Any]) -> None:
    """Valida retorno de ``run_full_pipeline`` (delega ao enforcement engine)."""
    validate_full_pipeline_contract(result)
