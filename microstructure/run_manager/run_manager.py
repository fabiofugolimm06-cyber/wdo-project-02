"""
microstructure/run_manager/run_manager.py — gestão padronizada de RUNS.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from microstructure.strategy_config import (
    save_strategy_config,
    validate_strategy_config,
)

_METADATA_FILENAME = "run_metadata.json"
_REQUIRED_METADATA_KEYS = frozenset({"run_id", "timestamp", "config"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_run_id(when: datetime | None = None) -> tuple[str, str]:
    when = when or _utc_now()
    run_id = f"run_{when.strftime('%Y%m%d_%H%M%S')}"
    timestamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    return run_id, timestamp


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


def _validate_base_dir(base_dir: str | Path) -> Path:
    if base_dir is None or not str(base_dir).strip():
        raise ValueError("run_manager: base_dir vazio.")
    path = Path(base_dir)
    if path.is_file():
        raise ValueError(f"run_manager: base_dir aponta para arquivo: {path}")
    return path


def create_run_directory(
    base_dir: str | Path = "runs",
    run_id: str | None = None,
) -> dict[str, str]:
    """
    Cria diretório de run em ``{base_dir}/run_YYYYMMDD_HHMMSS/``.

    Se o diretório já existir, acrescenta sufixo ``_001``, ``_002``, ...
    """
    root = _validate_base_dir(base_dir)
    root.mkdir(parents=True, exist_ok=True)

    if run_id is None:
        run_id, _ = _format_run_id()

    candidate = root / run_id
    if not candidate.exists():
        candidate.mkdir(parents=True)
        return {
            "run_id": run_id,
            "run_directory": str(candidate.resolve()),
        }

    suffix = 1
    while True:
        alt_id = f"{run_id}_{suffix:03d}"
        alt_path = root / alt_id
        if not alt_path.exists():
            alt_path.mkdir(parents=True)
            return {
                "run_id": alt_id,
                "run_directory": str(alt_path.resolve()),
            }
        suffix += 1


def _validate_metadata(metadata: dict[str, Any]) -> None:
    if not isinstance(metadata, dict):
        raise TypeError("save_run_metadata: metadata deve ser dict.")
    missing = _REQUIRED_METADATA_KEYS - set(metadata.keys())
    if missing:
        raise ValueError(
            f"save_run_metadata: chaves ausentes: {sorted(missing)}."
        )
    validate_strategy_config(metadata["config"])


def save_run_metadata(
    run_directory: str | Path,
    metadata: dict[str, Any],
) -> dict[str, str]:
    """Persiste ``run_metadata.json`` no diretório da run."""
    _validate_metadata(metadata)
    run_path = Path(run_directory)
    if not run_path.is_dir():
        raise ValueError(
            f"save_run_metadata: run_directory não existe: {run_path}"
        )

    file_path = run_path / _METADATA_FILENAME
    with file_path.open("w", encoding="utf-8") as fh:
        json.dump(_json_safe(metadata), fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return {"filepath": str(file_path.resolve())}


def load_run_metadata(run_directory: str | Path) -> dict[str, Any]:
    """Carrega ``run_metadata.json``."""
    run_path = Path(run_directory)
    file_path = run_path / _METADATA_FILENAME
    if not file_path.is_file():
        raise FileNotFoundError(
            f"load_run_metadata: metadata não encontrado: {file_path}"
        )

    with file_path.open("r", encoding="utf-8") as fh:
        metadata = json.load(fh)

    _validate_metadata(metadata)
    return metadata


def create_run(
    strategy_config: dict[str, Any],
    base_dir: str | Path = "runs",
) -> dict[str, Any]:
    """
    Cria run completa: diretório + metadata + ``strategy_config.json``.

    Parameters
    ----------
    strategy_config : config validada (Strategy Config v1).

    Returns
    -------
    dict com ``run_id``, ``timestamp``, ``run_directory``, ``metadata_path``,
    ``config_path``.
    """
    validate_strategy_config(strategy_config)

    run_id, timestamp = _format_run_id()
    dir_info = create_run_directory(base_dir=base_dir, run_id=run_id)
    run_directory = dir_info["run_directory"]
    final_run_id = dir_info["run_id"]

    metadata = {
        "run_id": final_run_id,
        "timestamp": timestamp,
        "config": strategy_config,
    }
    meta_saved = save_run_metadata(run_directory, metadata)
    config_saved = save_strategy_config(run_directory, strategy_config)

    return {
        "run_id": final_run_id,
        "timestamp": timestamp,
        "run_directory": run_directory,
        "metadata_path": meta_saved["filepath"],
        "config_path": config_saved["filepath"],
    }
