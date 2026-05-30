"""
microstructure/model_registry/registry.py — registro centralizado de modelos.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REGISTRY_FILENAME = "model_registry.json"
_REQUIRED_KEYS = frozenset({
    "model_id",
    "timestamp",
    "model_name",
    "model_type",
    "parameters",
    "metrics",
})


def _validate_output_dir(output_dir: str | Path) -> Path:
    if output_dir is None:
        raise ValueError("model_registry: output_dir não pode ser None.")
    if not isinstance(output_dir, (str, Path)):
        raise TypeError(
            f"model_registry: output_dir deve ser str ou Path, "
            f"got {type(output_dir).__name__}."
        )
    path = Path(output_dir)
    if not str(output_dir).strip():
        raise ValueError("model_registry: output_dir vazio.")
    if path.is_file():
        raise ValueError(f"model_registry: output_dir aponta para arquivo: {path}")
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


def _validate_entry(entry: dict[str, Any]) -> None:
    missing = _REQUIRED_KEYS - set(entry.keys())
    if missing:
        raise ValueError(
            f"model_registry: entrada inválida, chaves ausentes: {sorted(missing)}."
        )


class ModelRegistry:
    """Registro em memória de modelos treinados."""

    def __init__(self) -> None:
        self._models: list[dict[str, Any]] = []

    def register_model(
        self,
        model_name: str,
        model_type: str,
        parameters: dict[str, Any],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        if not model_name or not str(model_name).strip():
            raise ValueError("register_model: model_name vazio.")
        if not model_type or not str(model_type).strip():
            raise ValueError("register_model: model_type vazio.")
        if not isinstance(parameters, dict):
            raise TypeError("register_model: parameters deve ser dict.")
        if not isinstance(metrics, dict):
            raise TypeError("register_model: metrics deve ser dict.")

        entry = {
            "model_id": str(uuid.uuid4()),
            "timestamp": _utc_timestamp(),
            "model_name": str(model_name).strip(),
            "model_type": str(model_type).strip(),
            "parameters": parameters,
            "metrics": metrics,
        }
        _validate_entry(entry)
        self._models.append(entry)
        return entry

    def list_models(self) -> list[dict[str, Any]]:
        return [dict(m) for m in self._models]

    def get_best_model(self, metric: str = "sharpe") -> dict[str, Any]:
        if not self._models:
            raise ValueError("get_best_model: registro vazio.")

        def _score(model: dict[str, Any]) -> float:
            value = model.get("metrics", {}).get(metric)
            if value is None:
                return float("-inf")
            if isinstance(value, str):
                if value in ("inf", "+inf"):
                    return float("inf")
                if value == "-inf":
                    return float("-inf")
                try:
                    return float(value)
                except ValueError:
                    return float("-inf")
            try:
                return float(value)
            except (TypeError, ValueError):
                return float("-inf")

        return max(self._models, key=_score)

    def save_registry(self, output_dir: str | Path) -> dict[str, str]:
        out_path = _validate_output_dir(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        file_path = out_path / _REGISTRY_FILENAME
        payload = {"version": 1, "models": self._models}

        with file_path.open("w", encoding="utf-8") as fh:
            json.dump(_json_safe(payload), fh, indent=2, ensure_ascii=False)
            fh.write("\n")

        return {"filepath": str(file_path.resolve())}

    def load_from_dir(self, output_dir: str | Path) -> None:
        out_path = _validate_output_dir(output_dir)
        file_path = out_path / _REGISTRY_FILENAME
        if not file_path.is_file():
            self._models = []
            return

        with file_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        if not isinstance(data, dict) or "models" not in data:
            raise ValueError(
                "load_registry: JSON inválido — esperado objeto com chave 'models'."
            )
        models = data["models"]
        if not isinstance(models, list):
            raise ValueError("load_registry: 'models' deve ser lista.")

        for entry in models:
            _validate_entry(entry)
        self._models = models

    def clear(self) -> None:
        self._models = []


_active_registry = ModelRegistry()


def reset_registry() -> None:
    """Limpa o registro em memória (uso em testes)."""
    _active_registry.clear()


def register_model(
    model_name: str,
    model_type: str,
    parameters: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return _active_registry.register_model(
        model_name, model_type, parameters, metrics
    )


def list_models() -> list[dict[str, Any]]:
    return _active_registry.list_models()


def get_best_model(metric: str = "sharpe") -> dict[str, Any]:
    return _active_registry.get_best_model(metric=metric)


def save_registry(output_dir: str | Path) -> dict[str, str]:
    return _active_registry.save_registry(output_dir)


def load_registry(output_dir: str | Path) -> list[dict[str, Any]]:
    _active_registry.load_from_dir(output_dir)
    return _active_registry.list_models()
