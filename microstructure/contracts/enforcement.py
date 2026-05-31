"""
microstructure/contracts/enforcement.py — Contract Enforcement Engine (central).

Validação protobuf-like: schema rígido, sub-schemas isolados, falha imediata.
"""

from __future__ import annotations

from typing import Any, Mapping

from microstructure.contracts.registry import get_contract

_ML_CONTRACT = get_contract("ml_pipeline:v1")
_FULL_CONTRACT = get_contract("full_pipeline:v1")


class ContractViolationError(ValueError):
    """Violação de contrato de pipeline (ML ou E2E)."""


def validate_ml_contract(output: Mapping[str, Any]) -> None:
    """
    Valida saída de ``run_ml_pipeline_v1`` contra ``ml_pipeline_contract_v1``.

    - Top-level exatamente as chaves do contrato v1
    - ``metrics`` só classificação (accuracy, precision, recall, f1)
    - Proibido qualquer métrica de backtest (sharpe, pnl, drawdown, …)
    - Proibidos blocos E2E no top-level
    """
    if not isinstance(output, Mapping):
        raise ContractViolationError(
            "validate_ml_contract: output deve ser mapping."
        )

    e2e_blocks = frozenset(output.keys()) & frozenset({
        "backtest_metrics",
        "execution_metrics",
        "model_metrics",
        "features_shape",
    })
    if e2e_blocks:
        raise ContractViolationError(
            "validate_ml_contract: blocos E2E não pertencem ao ML pipeline: "
            f"{sorted(e2e_blocks)}."
        )

    try:
        _ML_CONTRACT.validate_output(output)
    except ValueError as exc:
        raise ContractViolationError(str(exc)) from exc


def validate_full_pipeline_contract(output: Mapping[str, Any]) -> None:
    """
    Valida saída de ``run_full_pipeline`` contra ``full_pipeline_contract_v1``.

    Sub-schemas:
    - ``model_metrics`` — mesmo contrato ML (sem sharpe/pnl/drawdown)
    - ``execution_metrics`` — required mínimo + extras permitidos
    - ``backtest_metrics`` — required mínimo (inclui sharpe) + extras permitidos
    """
    if not isinstance(output, Mapping):
        raise ContractViolationError(
            "validate_full_pipeline_contract: output deve ser mapping."
        )

    try:
        _FULL_CONTRACT.validate_output(output)
    except ValueError as exc:
        raise ContractViolationError(str(exc)) from exc

    if "sharpe" not in output.get("backtest_metrics", {}):
        raise ContractViolationError(
            "validate_full_pipeline_contract: backtest_metrics deve incluir 'sharpe'."
        )

    model_keys = frozenset(output["model_metrics"].keys())
    forbidden_in_model = model_keys & _ML_CONTRACT.nested_schemas[0].forbidden_keys
    if forbidden_in_model:
        raise ContractViolationError(
            "validate_full_pipeline_contract: model_metrics contém chaves de backtest "
            f"{sorted(forbidden_in_model)}."
        )
