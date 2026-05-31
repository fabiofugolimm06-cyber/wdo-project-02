"""
microstructure/contracts/registry.py — Contract Registry central (fonte única de verdade).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

from microstructure.contracts.contract_models import PipelineContract
from microstructure.contracts.versions import (
    full_pipeline_contract_v1,
    ml_pipeline_contract_v1,
)

# Tipos de contrato suportados pelo sistema (evolução: v2, v3 via registry)
CONTRACT_TYPES: Final[tuple[str, ...]] = ("ml_pipeline", "full_pipeline")

# Versão ativa por tipo (resolver automático: tipo → registry key)
_ACTIVE_VERSIONS: Final[dict[str, str]] = {
    "ml_pipeline": "v1",
    "full_pipeline": "v1",
}


class ContractRegistryError(Exception):
    """Erro base do registry de contratos."""


class ContractNotFoundError(ContractRegistryError):
    """``contract_id`` ou registry key não encontrada."""


class ContractDuplicateError(ContractRegistryError):
    """Tentativa de registro duplicado ou overwrite."""


class ContractRegistryFrozenError(ContractRegistryError):
    """Registry imutável após ``freeze()`` — sem overwrite silencioso."""


class ContractRegistry:
    """
    Central registry de contratos versionados do sistema.

    Regras
    ------
    - Registro imutável após ``freeze()``
    - Sem chaves duplicadas (registry id ou ``contract_id``)
    - Acesso preferencial via ``get_contract()`` / singleton ``contract_registry``
    """

    def __init__(self) -> None:
        self._contracts: dict[str, PipelineContract] = {}
        self._by_contract_id: dict[str, str] = {}
        self._frozen = False

    def register(self, registry_key: str, contract: PipelineContract) -> None:
        """
        Registra um contrato sob ``registry_key`` (ex. ``ml_pipeline:v1``).

        Raises
        ------
        ContractRegistryFrozenError
        ContractDuplicateError
        """
        if self._frozen:
            raise ContractRegistryFrozenError(
                "ContractRegistry: registro bloqueado após freeze(). "
                "Crie nova versão (v2) em vez de alterar o registry ativo."
            )
        if registry_key in self._contracts:
            raise ContractDuplicateError(
                f"ContractRegistry: registry_key duplicada {registry_key!r}."
            )
        if contract.contract_id in self._by_contract_id:
            existing = self._by_contract_id[contract.contract_id]
            raise ContractDuplicateError(
                f"ContractRegistry: contract_id {contract.contract_id!r} "
                f"já registrado como {existing!r}."
            )
        self._contracts[registry_key] = contract
        self._by_contract_id[contract.contract_id] = registry_key

    def freeze(self) -> None:
        """Torna o registry imutável (sem novos registros)."""
        self._frozen = True

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    def _resolve_registry_key(self, contract_id: str) -> str:
        if contract_id in self._contracts:
            return contract_id
        if contract_id in self._by_contract_id:
            return self._by_contract_id[contract_id]
        if ":" not in contract_id:
            active = _ACTIVE_VERSIONS.get(contract_id)
            if active is not None:
                candidate = f"{contract_id}:{active}"
                if candidate in self._contracts:
                    return candidate
        raise ContractNotFoundError(
            f"ContractRegistry: contrato não encontrado {contract_id!r}. "
            f"Disponíveis: {sorted(self._contracts.keys())}."
        )

    def get_contract(self, contract_id: str) -> PipelineContract:
        """
        Obtém contrato por registry key (``ml_pipeline:v1``),
        ``contract_id`` (``ml_pipeline_contract_v1``) ou tipo ativo (``ml_pipeline``).
        """
        self.validate_contract_exists(contract_id)
        key = self._resolve_registry_key(contract_id)
        return self._contracts[key]

    def list_contracts(self) -> tuple[str, ...]:
        """Lista todas as registry keys registradas."""
        return tuple(sorted(self._contracts.keys()))

    def list_contract_ids(self) -> tuple[str, ...]:
        """Lista ``contract_id`` de todos os contratos."""
        return tuple(
            sorted(c.contract_id for c in self._contracts.values())
        )

    def get_active_version(self, contract_type: str) -> str:
        """
        Retorna versão ativa para um tipo (ex. ``ml_pipeline`` → ``v1``).

        Raises
        ------
        ContractNotFoundError : tipo desconhecido.
        """
        if contract_type not in _ACTIVE_VERSIONS:
            raise ContractNotFoundError(
                f"ContractRegistry: contract_type desconhecido {contract_type!r}. "
                f"Tipos: {list(_ACTIVE_VERSIONS)}."
            )
        return _ACTIVE_VERSIONS[contract_type]

    def get_active_contract(self, contract_type: str) -> PipelineContract:
        """Resolve tipo → versão ativa → ``PipelineContract``."""
        version = self.get_active_version(contract_type)
        return self.get_contract(f"{contract_type}:{version}")

    def validate_contract_exists(self, contract_id: str) -> bool:
        """
        Verifica se o contrato existe.

        Raises
        ------
        ContractNotFoundError : se não existir.
        """
        try:
            self._resolve_registry_key(contract_id)
        except ContractNotFoundError:
            raise
        return True

    def as_readonly_map(self) -> MappingProxyType[str, PipelineContract]:
        """Vista somente-leitura do mapa interno (imutável após freeze)."""
        return MappingProxyType(dict(self._contracts))


def _build_default_contracts() -> dict[str, PipelineContract]:
    return {
        "ml_pipeline:v1": ml_pipeline_contract_v1,
        "full_pipeline:v1": full_pipeline_contract_v1,
    }


CONTRACTS: Final[dict[str, PipelineContract]] = _build_default_contracts()


def _build_global_registry() -> ContractRegistry:
    registry = ContractRegistry()
    for key, contract in CONTRACTS.items():
        registry.register(key, contract)
    registry.freeze()
    return registry


contract_registry: Final[ContractRegistry] = _build_global_registry()


def get_contract(contract_id: str) -> PipelineContract:
    """Atalho para ``contract_registry.get_contract`` (API pública preferencial)."""
    return contract_registry.get_contract(contract_id)


# Re-export explícito dos contratos v1 (compatibilidade; preferir get_contract)
ml_pipeline_contract_v1 = contract_registry.get_contract("ml_pipeline:v1")
full_pipeline_contract_v1 = contract_registry.get_contract("full_pipeline:v1")
