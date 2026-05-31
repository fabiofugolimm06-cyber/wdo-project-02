"""
config_registry.py — registry append-only de ConfigContract.
"""

from __future__ import annotations

from typing import Any

from src.config.config_contract import (
    WDO_ACTIVE_CONFIG_ID,
    WDO_ACTIVE_CONFIG_VERSION,
    ConfigContract,
    build_canonical_config_schema,
)


class ConfigRegistryError(Exception):
    """Erro base do config registry."""


class ConfigNotFoundError(ConfigRegistryError):
    """Config não encontrada."""


class ConfigDuplicateError(ConfigRegistryError):
    """Overwrite proibido."""


class ConfigRegistry:
    """Registry central de configs versionadas (append-only)."""

    def __init__(self) -> None:
        self._by_key: dict[str, ConfigContract] = {}
        self._active: dict[str, str] = {}

    def register_config(self, contract: ConfigContract) -> None:
        key = contract.registry_key
        if key in self._by_key:
            raise ConfigDuplicateError(
                f"ConfigRegistry: config duplicada {key!r} (sem overwrite)."
            )
        self._by_key[key] = contract

    def set_active(self, config_id: str, version: str) -> None:
        key = f"{config_id}:{version}"
        if key not in self._by_key:
            raise ConfigNotFoundError(f"ConfigRegistry: config ausente {key!r}.")
        self._active[config_id] = version

    def get_config(
        self,
        config_id: str,
        version: str | None = None,
    ) -> ConfigContract:
        if version is None:
            version = self._active.get(config_id)
            if version is None:
                raise ConfigNotFoundError(
                    f"ConfigRegistry: versão ativa ausente para {config_id!r}."
                )
        key = f"{config_id}:{version}"
        try:
            return self._by_key[key]
        except KeyError as exc:
            raise ConfigNotFoundError(
                f"ConfigRegistry: config não encontrada {key!r}."
            ) from exc

    def list_configs(self, config_id: str | None = None) -> list[ConfigContract]:
        items = list(self._by_key.values())
        if config_id is not None:
            items = [c for c in items if c.config_id == config_id]
        return sorted(items, key=lambda c: (c.config_id, c.version))

    def validate_config_integrity(self) -> dict[str, Any]:
        errors: list[str] = []
        from src.config.config_contract import compute_config_hash

        for key, contract in self._by_key.items():
            if compute_config_hash(contract.schema) != contract.hash:
                errors.append(f"{key}: hash inconsistente.")
            if contract.registry_key != key:
                errors.append(f"{key}: registry_key inconsistente.")

        for config_id, version in self._active.items():
            active_key = f"{config_id}:{version}"
            if active_key not in self._by_key:
                errors.append(f"active config ausente: {active_key}.")

        return {
            "valid": len(errors) == 0,
            "config_count": len(self._by_key),
            "errors": sorted(errors),
        }


def bootstrap_production_config_registry(
    *,
    environment: str = "ci",
) -> ConfigRegistry:
    registry = ConfigRegistry()
    schema = build_canonical_config_schema(environment=environment)
    contract = ConfigContract.create(
        config_id=WDO_ACTIVE_CONFIG_ID,
        version=WDO_ACTIVE_CONFIG_VERSION,
        schema=schema,
        locked=True,
    )
    registry.register_config(contract)
    registry.set_active(WDO_ACTIVE_CONFIG_ID, WDO_ACTIVE_CONFIG_VERSION)
    return registry
