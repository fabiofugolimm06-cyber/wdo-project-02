"""Contratos versionados — camada ``src/contracts``."""

from src.contracts.data import (
    DataContract,
    DataContractError,
    DataContractIntegrityError,
    DatasetDuplicateError,
    DatasetNotFoundError,
    DatasetRegistry,
    DatasetRegistryError,
    OHLCV_SCHEMA_V1,
    generate_dataset_hash,
    generate_fingerprint,
    generate_schema_hash,
)

__all__ = [
    "DataContract",
    "DataContractError",
    "DataContractIntegrityError",
    "DatasetDuplicateError",
    "DatasetNotFoundError",
    "DatasetRegistry",
    "DatasetRegistryError",
    "OHLCV_SCHEMA_V1",
    "generate_dataset_hash",
    "generate_fingerprint",
    "generate_schema_hash",
]
