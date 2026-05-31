"""
data_contract.py — entidade versionada de dataset OHLCV (Data Contract v1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from src.contracts.data.dataset_fingerprint import (
    generate_dataset_hash,
    generate_fingerprint,
    generate_schema_hash,
)

OHLCV_SCHEMA_V1: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "wdo.ohlcv.schema.v1",
    "title": "WDO OHLCV v1",
    "type": "object",
    "required": ["columns", "index", "dtypes"],
    "properties": {
        "columns": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 5,
            "maxItems": 5,
            "const": ["abertura", "alta", "baixa", "fechamento", "volume"],
        },
        "index": {"type": "string", "const": "datetime64[ns]"},
        "dtypes": {
            "type": "object",
            "required": ["abertura", "alta", "baixa", "fechamento", "volume"],
            "properties": {
                "abertura": {"type": "string"},
                "alta": {"type": "string"},
                "baixa": {"type": "string"},
                "fechamento": {"type": "string"},
                "volume": {"type": "string"},
            },
        },
    },
    "additionalProperties": False,
}

ALLOWED_MISSING_DATA_POLICIES: frozenset[str] = frozenset(
    {"fail", "drop", "forward_fill", "explicit_gap"}
)


class DataContractError(Exception):
    """Erro base da Data Contract Layer."""


class DataContractIntegrityError(DataContractError):
    """Hash/fingerprint/schema inconsistente."""


@dataclass(frozen=True)
class DataContract:
    """
    Contrato imutável de dataset OHLCV versionado.

    ``dataset_hash`` reflete conteúdo + ordem temporal.
    ``fingerprint`` inclui também schema e normalização.
    """

    dataset_id: str
    symbol: str
    timeframe: str
    source: str

    schema: dict[str, Any]
    schema_hash: str

    dataset_hash: str
    fingerprint: str

    version: str

    normalization_version: str
    missing_data_policy: str

    lineage_enabled: bool

    def __post_init__(self) -> None:
        if not self.dataset_id.strip():
            raise DataContractIntegrityError("dataset_id vazio.")
        if not self.version.strip():
            raise DataContractIntegrityError("version vazia.")
        if self.missing_data_policy not in ALLOWED_MISSING_DATA_POLICIES:
            raise DataContractIntegrityError(
                f"missing_data_policy inválida: {self.missing_data_policy!r}."
            )
        _validate_json_schema_compatible(self.schema)
        expected_schema_hash = generate_schema_hash(self.schema)
        if self.schema_hash != expected_schema_hash:
            raise DataContractIntegrityError(
                "schema_hash não corresponde ao schema."
            )

    @property
    def registry_key(self) -> str:
        return f"{self.dataset_id}:{self.version}"

    @classmethod
    def from_dataframe(
        cls,
        data: pd.DataFrame,
        *,
        dataset_id: str,
        symbol: str,
        timeframe: str,
        source: str,
        version: str,
        schema: Mapping[str, Any] | None = None,
        normalization_version: str = "none:v1",
        missing_data_policy: str = "fail",
        lineage_enabled: bool = True,
    ) -> DataContract:
        """
        Constrói contrato a partir de OHLCV, calculando hashes determinísticos.
        """
        schema_dict = dict(schema or OHLCV_SCHEMA_V1)
        schema_hash = generate_schema_hash(schema_dict)
        dataset_hash = generate_dataset_hash(data)
        fingerprint = generate_fingerprint(
            data,
            schema_dict,
            normalization_version=normalization_version,
        )
        return cls(
            dataset_id=dataset_id,
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            schema=schema_dict,
            schema_hash=schema_hash,
            dataset_hash=dataset_hash,
            fingerprint=fingerprint,
            version=version,
            normalization_version=normalization_version,
            missing_data_policy=missing_data_policy,
            lineage_enabled=lineage_enabled,
        )

    def verify_against_data(self, data: pd.DataFrame) -> None:
        """
        Recalcula hashes e falha se divergirem do contrato.

        Raises
        ------
        DataContractIntegrityError
        """
        expected_dataset_hash = generate_dataset_hash(data)
        if expected_dataset_hash != self.dataset_hash:
            raise DataContractIntegrityError(
                "dataset_hash não corresponde aos dados."
            )
        expected_fingerprint = generate_fingerprint(
            data,
            self.schema,
            normalization_version=self.normalization_version,
        )
        if expected_fingerprint != self.fingerprint:
            raise DataContractIntegrityError(
                "fingerprint não corresponde aos dados/schema/normalização."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "source": self.source,
            "schema": dict(self.schema),
            "schema_hash": self.schema_hash,
            "dataset_hash": self.dataset_hash,
            "fingerprint": self.fingerprint,
            "version": self.version,
            "normalization_version": self.normalization_version,
            "missing_data_policy": self.missing_data_policy,
            "lineage_enabled": self.lineage_enabled,
        }


def _validate_json_schema_compatible(schema: Mapping[str, Any]) -> None:
    if not isinstance(schema, dict):
        raise DataContractIntegrityError("schema deve ser dict.")
    if not schema:
        raise DataContractIntegrityError("schema vazio.")
    has_type = "type" in schema
    has_schema_uri = "$schema" in schema
    has_properties = "properties" in schema
    if not (has_type or has_schema_uri or has_properties):
        raise DataContractIntegrityError(
            "schema deve ser JSON-schema compatible "
            "(type, $schema ou properties)."
        )
