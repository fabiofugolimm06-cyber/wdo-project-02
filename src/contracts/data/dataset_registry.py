"""
dataset_registry.py — registry append-only de DataContract (imutável após registro).
"""

from __future__ import annotations

from typing import Any

from src.contracts.data.data_contract import DataContract, DataContractIntegrityError


class DatasetRegistryError(Exception):
    """Erro base do registry de datasets."""


class DatasetNotFoundError(DatasetRegistryError):
    """``dataset_id`` / versão não encontrados."""


class DatasetDuplicateError(DatasetRegistryError):
    """Fingerprint ou registry key duplicada."""


class DatasetRegistry:
    """
    Registry central de datasets OHLCV versionados.

    Regras
    ------
    - Append-only: contratos imutáveis após ``register``
    - Fingerprint único globalmente
    - ``(dataset_id, version)`` único
    - Nova versão obrigatória para evolução do mesmo ``dataset_id``
    """

    def __init__(self) -> None:
        self._by_key: dict[str, DataContract] = {}
        self._by_fingerprint: dict[str, str] = {}
        self._versions_by_id: dict[str, tuple[str, ...]] = {}

    def register(self, contract: DataContract) -> None:
        """
        Registra um contrato imutável.

        Raises
        ------
        DatasetDuplicateError
        DataContractIntegrityError
        """
        key = contract.registry_key
        if key in self._by_key:
            raise DatasetDuplicateError(
                f"DatasetRegistry: registry key duplicada {key!r}."
            )
        if contract.fingerprint in self._by_fingerprint:
            existing = self._by_fingerprint[contract.fingerprint]
            raise DatasetDuplicateError(
                f"DatasetRegistry: fingerprint duplicado "
                f"{contract.fingerprint!r} (já em {existing!r})."
            )

        self._by_key[key] = contract
        self._by_fingerprint[contract.fingerprint] = key
        versions = self._versions_by_id.get(contract.dataset_id, ())
        if contract.version in versions:
            raise DatasetDuplicateError(
                f"DatasetRegistry: versão duplicada "
                f"{contract.dataset_id!r} / {contract.version!r}."
            )
        self._versions_by_id[contract.dataset_id] = tuple(
            sorted(versions + (contract.version,))
        )

    def get(self, dataset_id: str, version: str | None = None) -> DataContract:
        """
        Obtém contrato por ``dataset_id`` e versão.

        Se ``version`` for None, retorna a versão lexicograficamente mais recente
        registrada para o ``dataset_id``.
        """
        if version is None:
            versions = self._versions_by_id.get(dataset_id)
            if not versions:
                raise DatasetNotFoundError(
                    f"DatasetRegistry: dataset não encontrado {dataset_id!r}."
                )
            version = sorted(versions)[-1]

        key = f"{dataset_id}:{version}"
        try:
            return self._by_key[key]
        except KeyError as exc:
            raise DatasetNotFoundError(
                f"DatasetRegistry: contrato não encontrado {key!r}."
            ) from exc

    def list(self, symbol: str | None = None) -> list[DataContract]:
        """Lista contratos registrados, opcionalmente filtrados por ``symbol``."""
        contracts = list(self._by_key.values())
        if symbol is not None:
            contracts = [c for c in contracts if c.symbol == symbol]
        return sorted(contracts, key=lambda c: (c.dataset_id, c.version))

    def validate_integrity(self) -> dict[str, Any]:
        """
        Valida integridade interna do registry.

        Returns
        -------
        dict com ``valid``, contagens e ``errors``.
        """
        errors: list[str] = []
        fingerprints: list[str] = []
        keys: list[str] = []

        for key, contract in self._by_key.items():
            keys.append(key)
            fingerprints.append(contract.fingerprint)
            try:
                expected_schema_hash = contract.schema_hash
                from src.contracts.data.dataset_fingerprint import (
                    generate_schema_hash,
                )

                if generate_schema_hash(contract.schema) != expected_schema_hash:
                    errors.append(
                        f"{key}: schema_hash inconsistente com schema."
                    )
            except Exception as exc:  # noqa: BLE001 — agregação de erros CI
                errors.append(f"{key}: falha ao validar schema — {exc}.")

            if contract.registry_key != key:
                errors.append(f"{key}: registry_key inconsistente.")

        if len(set(fingerprints)) != len(fingerprints):
            errors.append("fingerprints duplicados detectados.")

        if len(set(keys)) != len(keys):
            errors.append("registry keys duplicadas detectadas.")

        for dataset_id, versions in self._versions_by_id.items():
            registered = [v for k, v in self._by_key.items() if k.startswith(f"{dataset_id}:")]
            if len(registered) != len(versions):
                errors.append(
                    f"{dataset_id}: índice de versões inconsistente."
                )

        return {
            "valid": len(errors) == 0,
            "dataset_count": len(self._by_key),
            "unique_fingerprints": len(set(fingerprints)),
            "errors": errors,
        }
