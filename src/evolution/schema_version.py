"""
schema_version.py — entidade versionada de schema (cadeia imutável).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from microstructure.contracts.contract_models import PipelineContract


class SchemaVersionError(Exception):
    """Erro base do schema version engine."""


class SchemaStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"


def compute_schema_hash(schema: Mapping[str, Any]) -> str:
    """Hash SHA256 determinístico de schema JSON-compatible."""
    payload = json.dumps(
        dict(schema),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SchemaVersion:
    """
    Versão imutável de schema com parent tracking obrigatório (exceto raiz).

    ``contract_id`` identifica a família (ex. ``ml_pipeline``).
    ``version`` é o identificador evolutivo (ex. ``v1``).
    """

    contract_id: str
    version: str
    parent_version: str | None
    schema: dict[str, Any]
    hash: str
    status: SchemaStatus

    def __post_init__(self) -> None:
        if not self.contract_id.strip():
            raise SchemaVersionError("contract_id vazio.")
        if not self.version.strip():
            raise SchemaVersionError("version vazia — versionamento obrigatório.")
        if not isinstance(self.status, SchemaStatus):
            object.__setattr__(self, "status", SchemaStatus(str(self.status)))
        expected = compute_schema_hash(self.schema)
        if self.hash != expected:
            raise SchemaVersionError(
                "hash inconsistente com schema (sem override permitido)."
            )

    @property
    def registry_key(self) -> str:
        return f"{self.contract_id}:{self.version}"

    @classmethod
    def create(
        cls,
        *,
        contract_id: str,
        version: str,
        schema: Mapping[str, Any],
        parent_version: str | None = None,
        status: SchemaStatus = SchemaStatus.ACTIVE,
    ) -> SchemaVersion:
        """Fabrica versão com hash calculado automaticamente."""
        schema_dict = dict(schema)
        return cls(
            contract_id=contract_id,
            version=version,
            parent_version=parent_version,
            schema=schema_dict,
            hash=compute_schema_hash(schema_dict),
            status=status,
        )

    @classmethod
    def from_pipeline_contract(
        cls,
        contract: PipelineContract,
        *,
        contract_id: str,
        version: str,
        parent_version: str | None = None,
        status: SchemaStatus = SchemaStatus.ACTIVE,
    ) -> SchemaVersion:
        """Converte ``PipelineContract`` em ``SchemaVersion``."""
        schema = contract.to_dict()
        schema["pipeline_contract_id"] = contract.contract_id
        schema["pipeline_semver"] = contract.version
        return cls.create(
            contract_id=contract_id,
            version=version,
            schema=schema,
            parent_version=parent_version,
            status=status,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "version": self.version,
            "parent_version": self.parent_version,
            "schema": dict(self.schema),
            "hash": self.hash,
            "status": self.status.value,
        }
