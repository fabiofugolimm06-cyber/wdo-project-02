"""
microstructure/contracts/compatibility.py — backward compatibility para outputs.
"""

from __future__ import annotations

from typing import Any, Mapping

from microstructure.contracts.contract_models import PipelineContract


def validate_compatibility(
    old_contract: PipelineContract,
    new_output: Mapping[str, Any],
    *,
    allow_controlled_additions: bool | None = None,
) -> None:
    """
    Garante que ``new_output`` ainda satisfaz um contrato anterior.

    Regras
    ------
    - Nunca permite remoção silenciosa de chaves obrigatórias do contrato antigo.
    - Chaves extras no top-level só se ``allow_controlled_additions`` ou
      ``old_contract.allow_extra_top_keys`` for True.
    - Blocos nested seguem ``allow_extra_keys`` do contrato antigo.

    Parameters
    ----------
    old_contract : contrato baseline (ex. ``ml_pipeline_contract_v1``).
    new_output : saída atual do pipeline.
    allow_controlled_additions : override explícito para adição de chaves top-level.

    Raises
    ------
    ValueError : incompatibilidade estrutural detectada.
    """
    allow_extra = (
        old_contract.allow_extra_top_keys
        if allow_controlled_additions is None
        else allow_controlled_additions
    )

    if not isinstance(new_output, Mapping):
        raise ValueError(
            f"validate_compatibility({old_contract.contract_id}): "
            f"new_output deve ser mapping."
        )

    keys = frozenset(new_output.keys())

    missing = old_contract.required_top_keys - keys
    if missing:
        raise ValueError(
            f"validate_compatibility({old_contract.contract_id}): "
            f"remoção silenciosa detectada — chaves ausentes {sorted(missing)}."
        )

    forbidden = keys & old_contract.forbidden_top_keys
    if forbidden:
        raise ValueError(
            f"validate_compatibility({old_contract.contract_id}): "
            f"chaves proibidas presentes {sorted(forbidden)}."
        )

    if not allow_extra:
        extra = keys - old_contract.required_top_keys
        if extra:
            raise ValueError(
                f"validate_compatibility({old_contract.contract_id}): "
                f"adição não controlada de chaves top-level {sorted(extra)}."
            )

    for nested in old_contract.nested_schemas:
        if nested.block_name not in new_output:
            raise ValueError(
                f"validate_compatibility({old_contract.contract_id}): "
                f"bloco '{nested.block_name}' ausente."
            )
        block = new_output[nested.block_name]
        if not isinstance(block, Mapping):
            raise ValueError(
                f"validate_compatibility({old_contract.contract_id}): "
                f"'{nested.block_name}' deve ser mapping."
            )

        block_keys = frozenset(block.keys())
        missing_nested = nested.required_keys - block_keys
        if missing_nested:
            raise ValueError(
                f"validate_compatibility({old_contract.contract_id}): "
                f"'{nested.block_name}' — remoção silenciosa {sorted(missing_nested)}."
            )

        forbidden_nested = block_keys & nested.forbidden_keys
        if forbidden_nested:
            raise ValueError(
                f"validate_compatibility({old_contract.contract_id}): "
                f"'{nested.block_name}' — chaves proibidas {sorted(forbidden_nested)}."
            )

        if not nested.allow_extra_keys:
            extra_nested = block_keys - nested.required_keys
            if extra_nested:
                raise ValueError(
                    f"validate_compatibility({old_contract.contract_id}): "
                    f"'{nested.block_name}' — adição não controlada "
                    f"{sorted(extra_nested)}."
                )

    # Validação completa de tipos/NaN via contrato (mesma lógica runtime)
    old_contract.validate_output(new_output)


def get_model_metrics_block(result: Mapping[str, Any]) -> Mapping[str, Any]:
    """
    Retorna o bloco de métricas de classificação ML.

    Compatível com:
    - ``run_ml_pipeline_v1`` → ``metrics``
    - ``run_full_pipeline`` → ``model_metrics``
    """
    if "metrics" in result:
        return result["metrics"]
    if "model_metrics" in result:
        return result["model_metrics"]
    raise KeyError(
        "Pipeline result has no ML metrics block. "
        "Expected 'metrics' (ML v1) or 'model_metrics' (E2E v1)."
    )


def get_backtest_metrics_block(result: Mapping[str, Any]) -> Mapping[str, Any]:
    """Retorna ``backtest_metrics`` (E2E) ou mapping vazio (ML isolado)."""
    block = result.get("backtest_metrics")
    if block is None:
        return {}
    if not isinstance(block, Mapping):
        raise TypeError("backtest_metrics deve ser mapping.")
    return block


def resolve_regression_metric(result: Mapping[str, Any], key: str) -> float:
    """
    Resolve métrica por nome — compatibilidade pós-refatoração.

    - Chaves ML (accuracy, precision, recall, f1) → bloco ML.
    - Chaves de backtest (sharpe, total_return, …) → ``backtest_metrics`` (E2E).
    """
    model_metrics = get_model_metrics_block(result)
    if key in model_metrics:
        return float(model_metrics[key])

    backtest = get_backtest_metrics_block(result)
    if key in backtest:
        return float(backtest[key])

    if key in {"sharpe", "total_return", "max_drawdown", "win_rate", "completed_trades"}:
        raise KeyError(
            f"'{key}' belongs to backtest_metrics (E2E pipeline). "
            "run_ml_pipeline_v1 does not produce backtest metrics — use run_full_pipeline."
        )
    raise KeyError(
        f"Metric '{key}' not found. ML keys: {sorted(model_metrics.keys())}; "
        f"backtest keys: {sorted(backtest.keys())}."
    )


def assert_ml_pipeline_regression_stable(
    out1: Mapping[str, Any],
    out2: Mapping[str, Any],
    *,
    epsilon: float = 1e-9,
) -> None:
    """
    Garante que duas execuções de ``run_ml_pipeline_v1`` são idênticas.

    Substitui asserts legados que liam ``metrics['sharpe']`` (removido do ML v1).
    """
    from microstructure.contracts.enforcement import validate_ml_contract
    from microstructure.contracts.pipeline_schemas import ML_METRIC_KEYS
    from microstructure.model.pipeline import pipeline_fingerprint

    validate_ml_contract(out1)
    validate_ml_contract(out2)

    if out1.keys() != out2.keys():
        raise AssertionError(
            f"ML pipeline keys diverged: {sorted(out1.keys())} vs {sorted(out2.keys())}"
        )

    metrics1 = get_model_metrics_block(out1)
    metrics2 = get_model_metrics_block(out2)
    if set(metrics1.keys()) != ML_METRIC_KEYS:
        raise AssertionError(
            f"metrics keys != ML_METRIC_KEYS: {sorted(metrics1.keys())}"
        )

    for key in ML_METRIC_KEYS:
        delta = abs(float(metrics1[key]) - float(metrics2[key]))
        if delta >= epsilon:
            raise AssertionError(
                f"metric {key!r} diverged: {metrics1[key]!r} vs {metrics2[key]!r}"
            )

    if pipeline_fingerprint(dict(out1)) != pipeline_fingerprint(dict(out2)):
        raise AssertionError("pipeline fingerprint diverged between runs")
