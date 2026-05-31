"""
microstructure/contracts/snapshot.py — serialização estrutural de saída de pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

DEFAULT_NUMERIC_EPSILON = 1e-9


def build_ml_pipeline_snapshot(
    output: Mapping[str, Any],
    *,
    contract_version: str = "1.0.0",
    contract_id: str = "ml_pipeline_contract_v1",
) -> dict[str, Any]:
    """Snapshot estrutural + métricas numéricas (sem arrays brutos)."""
    metrics = output["metrics"]
    return {
        "contract_id": contract_id,
        "contract_version": contract_version,
        "schema": {
            "top_keys": sorted(output.keys()),
            "metrics_keys": sorted(metrics.keys()),
        },
        "structure": {
            "n_ml": int(output["n_ml"]),
            "n_train": int(output["n_train"]),
            "n_test": int(output["n_test"]),
            "signals_len": int(len(output["signals"])),
            "proba_len": int(len(output["proba"])),
        },
        "metrics": {
            k: round(float(metrics[k]), 12) for k in sorted(metrics.keys())
        },
    }


def save_snapshot(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _round_numeric(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return round(float(value), 12)
    return value


def build_full_pipeline_snapshot(
    output: Mapping[str, Any],
    *,
    contract_version: str = "1.0.0",
    contract_id: str = "full_pipeline_contract_v1",
) -> dict[str, Any]:
    """Snapshot E2E: schema + métricas por sub-bloco (sem arrays)."""
    model = output["model_metrics"]
    execution = output["execution_metrics"]
    backtest = output["backtest_metrics"]
    return {
        "contract_id": contract_id,
        "contract_version": contract_version,
        "schema": {
            "top_keys": sorted(output.keys()),
            "model_metrics_keys": sorted(model.keys()),
            "execution_metrics_keys": sorted(execution.keys()),
            "backtest_metrics_keys": sorted(backtest.keys()),
        },
        "structure": {
            "features_shape": [int(output["features_shape"][0]), int(output["features_shape"][1])],
        },
        "model_metrics": {
            k: _round_numeric(model[k]) for k in sorted(model.keys())
        },
        "execution_metrics": {
            k: _round_numeric(execution[k]) for k in sorted(execution.keys())
        },
        "backtest_metrics": {
            k: _round_numeric(backtest[k]) for k in sorted(backtest.keys())
        },
    }


def compare_pipeline_snapshots(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    epsilon: float = DEFAULT_NUMERIC_EPSILON,
) -> list[str]:
    """
    Compara snapshots ML ou E2E.

    - ``schema`` / ``structure`` — igualdade estrita
    - blocos numéricos — tolerância ``epsilon`` por valor float
    """
    errors: list[str] = []

    if actual.get("contract_id") != expected.get("contract_id"):
        errors.append(
            f"contract_id: {actual.get('contract_id')!r} != {expected.get('contract_id')!r}"
        )

    for section in ("schema", "structure"):
        if actual.get(section) != expected.get(section):
            errors.append(
                f"{section} drift: {actual.get(section)} != {expected.get(section)}"
            )

    numeric_blocks = (
        "metrics",
        "model_metrics",
        "execution_metrics",
        "backtest_metrics",
    )
    for block in numeric_blocks:
        act_block = actual.get(block)
        exp_block = expected.get(block)
        if act_block is None and exp_block is None:
            continue
        if act_block is None or exp_block is None:
            errors.append(f"{block}: bloco ausente em actual ou expected")
            continue
        if set(act_block.keys()) != set(exp_block.keys()):
            errors.append(
                f"{block} keys drift: {sorted(act_block)} != {sorted(exp_block)}"
            )
            continue
        for key in sorted(exp_block.keys()):
            a, e = act_block[key], exp_block[key]
            if isinstance(e, (int, float)) and isinstance(a, (int, float)):
                if abs(float(a) - float(e)) > epsilon:
                    errors.append(
                        f"{block}.{key}: |{a} - {e}| > {epsilon}"
                    )
            elif a != e:
                errors.append(f"{block}.{key}: {a!r} != {e!r}")

    return errors


def compare_ml_snapshots(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    epsilon: float = DEFAULT_NUMERIC_EPSILON,
) -> list[str]:
    """Alias retrocompat — delega a ``compare_pipeline_snapshots``."""
    return compare_pipeline_snapshots(actual, expected, epsilon=epsilon)
