"""
microstructure/strategy_config/config.py — configuração versionada de estratégia.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG_VERSION = "1"
_CONFIG_FILENAME = "strategy_config.json"

_REQUIRED_TOP_KEYS = frozenset({
    "config_id",
    "timestamp",
    "config_version",
    "strategy_name",
    "parameters",
})

_REQUIRED_PARAMETER_SECTIONS = frozenset({
    "data",
    "labeling",
    "model",
    "backtest",
    "execution",
    "validation",
})


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def get_default_config(strategy_name: str = "wdo_default") -> dict[str, Any]:
    """
    Retorna configuração padrão alinhada aos defaults do pipeline (v1–v14).

    Parameters
    ----------
    strategy_name : identificador legível da estratégia.
    """
    if not strategy_name or not str(strategy_name).strip():
        raise ValueError("get_default_config: strategy_name vazio.")

    return {
        "config_id": str(uuid.uuid4()),
        "timestamp": _utc_timestamp(),
        "config_version": CONFIG_VERSION,
        "strategy_name": str(strategy_name).strip(),
        "parameters": {
            "data": {
                "price_col": "fechamento",
            },
            "labeling": {
                "horizon": 5,
            },
            "model": {
                "train_size": 0.70,
                "ml_threshold": 0.55,
            },
            "backtest": {
                "max_hold_bars": 5,
                "stop_loss": 0.01,
                "take_profit": 0.02,
                "cost_per_trade": 0.0001,
                "slippage": 0.00005,
            },
            "execution": {
                "initial_capital": 100_000.0,
                "position_size": 1.0,
            },
            "validation": {
                "walk_forward": {
                    "train_size": 0.70,
                    "step_size": 20,
                },
                "purged_kfold": {
                    "n_splits": 5,
                    "horizon": 5,
                    "embargo": 1,
                },
            },
        },
    }


def validate_strategy_config(config: dict[str, Any]) -> None:
    """
    Valida estrutura mínima da configuração.

    Raises
    ------
    ValueError / TypeError
    """
    if not isinstance(config, dict):
        raise TypeError("validate_strategy_config: config deve ser dict.")

    missing = _REQUIRED_TOP_KEYS - set(config.keys())
    if missing:
        raise ValueError(
            f"validate_strategy_config: chaves ausentes: {sorted(missing)}."
        )

    if not config.get("strategy_name"):
        raise ValueError("validate_strategy_config: strategy_name vazio.")

    params = config.get("parameters")
    if not isinstance(params, dict):
        raise TypeError("validate_strategy_config: parameters deve ser dict.")

    missing_sections = _REQUIRED_PARAMETER_SECTIONS - set(params.keys())
    if missing_sections:
        raise ValueError(
            f"validate_strategy_config: seções ausentes em parameters: "
            f"{sorted(missing_sections)}."
        )

    model = params["model"]
    train_size = model.get("train_size")
    if not isinstance(train_size, (int, float)) or not 0 < train_size < 1:
        raise ValueError(
            "validate_strategy_config: model.train_size deve estar em (0, 1)."
        )

    ml_threshold = model.get("ml_threshold")
    if not isinstance(ml_threshold, (int, float)) or not 0 <= ml_threshold <= 1:
        raise ValueError(
            "validate_strategy_config: model.ml_threshold deve estar em [0, 1]."
        )


def create_strategy_config(
    strategy_name: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Cria config a partir do default, com ``overrides`` mesclados em ``parameters``.

    ``overrides`` pode ser dict plano (ex.: ``{"horizon": 10}``) ou aninhado por seção.
    """
    config = get_default_config(strategy_name=strategy_name)
    if not overrides:
        validate_strategy_config(config)
        return config

    params = config["parameters"]
    for key, value in overrides.items():
        if key in _REQUIRED_PARAMETER_SECTIONS and isinstance(value, dict):
            params[key] = {**params.get(key, {}), **value}
        elif key in _REQUIRED_PARAMETER_SECTIONS:
            raise ValueError(
                f"create_strategy_config: seção '{key}' requer dict em overrides."
            )
        else:
            for section in params.values():
                if isinstance(section, dict) and key in section:
                    section[key] = value
                    break
            else:
                if "model" in params:
                    params["model"][key] = value

    validate_strategy_config(config)
    return config


def save_strategy_config(
    filepath: str | Path,
    config: dict[str, Any],
) -> dict[str, str]:
    """
    Persiste configuração em JSON (sobrescreve se existir).

    Compatível com diretórios de run que já contêm artifacts / experiments.
    """
    validate_strategy_config(config)
    path = Path(filepath)
    if path.is_dir():
        path = path / _CONFIG_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as fh:
        json.dump(_json_safe(config), fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return {"filepath": str(path.resolve())}


def load_strategy_config(filepath: str | Path) -> dict[str, Any]:
    """Carrega e valida configuração JSON."""
    path = Path(filepath)
    if path.is_dir():
        path = path / _CONFIG_FILENAME
    if not path.is_file():
        raise FileNotFoundError(f"load_strategy_config: arquivo não encontrado: {path}")

    with path.open("r", encoding="utf-8") as fh:
        config = json.load(fh)

    validate_strategy_config(config)
    return config


def flatten_parameters(config: dict[str, Any]) -> dict[str, Any]:
    """
    Achata ``parameters`` para uso em Experiment Tracking / Model Registry.

    Ex.: ``{"horizon": 5, "train_size": 0.7, "price_col": "fechamento", ...}``
    """
    validate_strategy_config(config)
    flat: dict[str, Any] = {}
    for section, values in config["parameters"].items():
        if isinstance(values, dict):
            for k, v in values.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        flat[f"{section}_{k}_{sk}"] = sv
                else:
                    flat[f"{section}_{k}"] = v
    return flat
