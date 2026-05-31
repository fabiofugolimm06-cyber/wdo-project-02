"""
config_contract.py — entidade imutável de configuração versionada.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

WDO_ACTIVE_CONFIG_ID = "wdo_system_config"
WDO_ACTIVE_CONFIG_VERSION = "v1"


class ConfigContractError(Exception):
    """Erro base do config contract."""


def compute_config_hash(schema: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(schema), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_canonical_config_schema(*, environment: str = "ci") -> dict[str, Any]:
    """Schema canônico de produção/CI — determinístico."""
    from microstructure.contracts.snapshot import DEFAULT_NUMERIC_EPSILON
    from microstructure.determinism import WDO_PROJECT_RANDOM_SEED

    return {
        "config_id": WDO_ACTIVE_CONFIG_ID,
        "environment": environment,
        "determinism": {
            "seed": int(WDO_PROJECT_RANDOM_SEED),
            "pythonhashseed": 42,
            "omp_num_threads": 1,
        },
        "pipeline": {
            "snapshot_runs": 20,
            "numeric_epsilon": float(DEFAULT_NUMERIC_EPSILON),
        },
        "gates": {
            "contract": True,
            "evolution": True,
            "data": True,
            "snapshot_spec": True,
            "system_lock": True,
        },
    }


@dataclass(frozen=True)
class ConfigContract:
    config_id: str
    version: str
    schema: dict[str, Any]
    hash: str
    locked: bool

    def __post_init__(self) -> None:
        if not self.config_id.strip():
            raise ConfigContractError("config_id vazio.")
        if not self.version.strip():
            raise ConfigContractError("version vazia — versionamento obrigatório.")
        expected = compute_config_hash(self.schema)
        if self.hash != expected:
            raise ConfigContractError("hash inconsistente com schema.")

    @property
    def registry_key(self) -> str:
        return f"{self.config_id}:{self.version}"

    @classmethod
    def create(
        cls,
        *,
        config_id: str,
        version: str,
        schema: Mapping[str, Any],
        locked: bool = False,
    ) -> ConfigContract:
        schema_dict = dict(schema)
        return cls(
            config_id=config_id,
            version=version,
            schema=schema_dict,
            hash=compute_config_hash(schema_dict),
            locked=locked,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_id": self.config_id,
            "version": self.version,
            "schema": dict(self.schema),
            "hash": self.hash,
            "locked": self.locked,
        }
