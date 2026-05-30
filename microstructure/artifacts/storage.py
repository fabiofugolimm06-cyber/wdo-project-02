"""
microstructure/artifacts/storage.py — persistência JSON de métricas do pipeline.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_ARTIFACT_FILES = (
    ("model_metrics", "model_metrics.json"),
    ("execution_metrics", "execution_metrics.json"),
    ("backtest_metrics", "backtest_metrics.json"),
    ("report_metrics", "report_metrics.json"),
)


def _validate_output_dir(output_dir: str | Path) -> Path:
    if output_dir is None:
        raise ValueError("save_pipeline_artifacts: output_dir não pode ser None.")
    if not isinstance(output_dir, (str, Path)):
        raise TypeError(
            f"save_pipeline_artifacts: output_dir deve ser str ou Path, "
            f"got {type(output_dir).__name__}."
        )
    path = Path(output_dir)
    text = str(output_dir).strip()
    if not text:
        raise ValueError("save_pipeline_artifacts: output_dir vazio.")
    if path.is_file():
        raise ValueError(
            f"save_pipeline_artifacts: output_dir aponta para arquivo: {path}"
        )
    return path


def _json_safe(value: Any) -> Any:
    """Converte valores não serializáveis em JSON (ex.: inf)."""
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


def save_pipeline_artifacts(
    output_dir: str | Path,
    pipeline_result: dict[str, Any],
) -> dict[str, list[str]]:
    """
    Persiste métricas do pipeline em JSON (sobrescreve se existir).

    Parameters
    ----------
    output_dir : diretório de saída (criado se não existir).
    pipeline_result : dict com chaves opcionais ``model_metrics``,
        ``execution_metrics``, ``backtest_metrics``, ``report_metrics``.

    Returns
    -------
    {"files_saved": [caminhos absolutos dos arquivos gerados]}
    """
    if not isinstance(pipeline_result, dict):
        raise TypeError(
            "save_pipeline_artifacts: pipeline_result deve ser dict."
        )

    out_path = _validate_output_dir(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    files_saved: list[str] = []

    for key, filename in _ARTIFACT_FILES:
        payload = pipeline_result.get(key, {})
        if not isinstance(payload, dict):
            raise ValueError(
                f"save_pipeline_artifacts: '{key}' deve ser dict, "
                f"got {type(payload).__name__}."
            )

        file_path = out_path / filename
        with file_path.open("w", encoding="utf-8") as fh:
            json.dump(_json_safe(payload), fh, indent=2, ensure_ascii=False)
            fh.write("\n")

        files_saved.append(str(file_path.resolve()))

    return {"files_saved": files_saved}
