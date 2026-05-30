"""
microstructure/experiments/tracker.py — rastreamento de experimentos (JSON).
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_EXPERIMENT_FILENAME_SUFFIX = ".json"
_REQUIRED_KEYS = frozenset({
    "experiment_id",
    "timestamp",
    "experiment_name",
    "parameters",
    "metrics",
})


def _validate_output_dir(output_dir: str | Path) -> Path:
    if output_dir is None:
        raise ValueError("experiments: output_dir não pode ser None.")
    if not isinstance(output_dir, (str, Path)):
        raise TypeError(
            f"experiments: output_dir deve ser str ou Path, got {type(output_dir).__name__}."
        )
    path = Path(output_dir)
    if not str(output_dir).strip():
        raise ValueError("experiments: output_dir vazio.")
    if path.is_file():
        raise ValueError(f"experiments: output_dir aponta para arquivo: {path}")
    return path


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        if math.isnan(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_experiment(
    experiment_name: str,
    parameters: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """
    Monta registro de experimento com id e timestamp automáticos.

    Parameters
    ----------
    experiment_name : nome legível do experimento.
    parameters : hiperparâmetros / config (ex.: horizon, train_size).
    metrics : resultados (ex.: report_metrics, model_metrics).

    Returns
    -------
    dict com ``experiment_id``, ``timestamp``, ``experiment_name``,
    ``parameters``, ``metrics``.
    """
    if not experiment_name or not str(experiment_name).strip():
        raise ValueError("create_experiment: experiment_name vazio.")
    if not isinstance(parameters, dict):
        raise TypeError("create_experiment: parameters deve ser dict.")
    if not isinstance(metrics, dict):
        raise TypeError("create_experiment: metrics deve ser dict.")

    return {
        "experiment_id": str(uuid.uuid4()),
        "timestamp": _utc_timestamp(),
        "experiment_name": str(experiment_name).strip(),
        "parameters": parameters,
        "metrics": metrics,
    }


def _validate_experiment_data(experiment_data: dict[str, Any]) -> None:
    if not isinstance(experiment_data, dict):
        raise TypeError("save_experiment: experiment_data deve ser dict.")
    missing = _REQUIRED_KEYS - set(experiment_data.keys())
    if missing:
        raise ValueError(
            f"save_experiment: chaves obrigatórias ausentes: {sorted(missing)}."
        )


def save_experiment(
    output_dir: str | Path,
    experiment_data: dict[str, Any],
) -> dict[str, str]:
    """
    Persiste experimento em ``{output_dir}/{experiment_id}.json``.

    Sobrescreve se o arquivo já existir. Compatível com runs que também usam
    ``save_pipeline_artifacts`` no mesmo ``output_dir`` (artefatos separados).

    Returns
    -------
    {"filepath": caminho absoluto do JSON salvo}
    """
    _validate_experiment_data(experiment_data)
    out_path = _validate_output_dir(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    exp_id = str(experiment_data["experiment_id"])
    file_path = out_path / f"{exp_id}{_EXPERIMENT_FILENAME_SUFFIX}"

    with file_path.open("w", encoding="utf-8") as fh:
        json.dump(_json_safe(experiment_data), fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return {"filepath": str(file_path.resolve())}


def load_experiment(filepath: str | Path) -> dict[str, Any]:
    """Carrega experimento a partir de arquivo JSON."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"load_experiment: arquivo não encontrado: {path}")

    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError("load_experiment: JSON deve ser um objeto.")

    missing = _REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(
            f"load_experiment: chaves obrigatórias ausentes: {sorted(missing)}."
        )

    return data


def list_experiments(output_dir: str | Path) -> list[dict[str, Any]]:
    """
    Lista experimentos salvos em ``output_dir``.

    Ignora artefatos ``*_metrics.json`` do Stage 12 (ARTIFACTS V1).

    Returns
    -------
    Lista ordenada por ``timestamp`` (crescente), cada item com metadados
    e ``filepath``.
    """
    out_path = _validate_output_dir(output_dir)
    if not out_path.exists():
        return []

    artifact_names = {
        "model_metrics.json",
        "execution_metrics.json",
        "backtest_metrics.json",
        "report_metrics.json",
    }

    summaries: list[dict[str, Any]] = []

    for file_path in sorted(out_path.glob(f"*{_EXPERIMENT_FILENAME_SUFFIX}")):
        if file_path.name in artifact_names:
            continue
        try:
            data = load_experiment(file_path)
        except (json.JSONDecodeError, ValueError):
            continue

        summaries.append({
            "experiment_id": data["experiment_id"],
            "timestamp": data["timestamp"],
            "experiment_name": data["experiment_name"],
            "filepath": str(file_path.resolve()),
        })

    summaries.sort(key=lambda x: x["timestamp"])
    return summaries
