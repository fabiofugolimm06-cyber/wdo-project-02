"""
evolution_registry.py — registry imutável de cadeias ``SchemaVersion``.
"""

from __future__ import annotations

from typing import Any

from src.evolution.schema_version import SchemaStatus, SchemaVersion


class EvolutionRegistryError(Exception):
    """Erro base do evolution registry."""


class SchemaNotFoundError(EvolutionRegistryError):
    """Versão não encontrada."""


class SchemaVersionDuplicateError(EvolutionRegistryError):
    """Tentativa de overwrite (proibido)."""


class EvolutionRegistry:
    """
    Registry append-only de versões de schema.

    Regras
    ------
    - Nenhuma versão sobrescreve anterior
    - Parent tracking obrigatório (exceto raiz)
    - Cadeia imutável por ``contract_id``
    """

    def __init__(self) -> None:
        self._versions: dict[str, SchemaVersion] = {}
        self._by_contract: dict[str, list[str]] = {}

    def register_version(self, schema_version: SchemaVersion) -> None:
        key = schema_version.registry_key
        if key in self._versions:
            raise SchemaVersionDuplicateError(
                f"EvolutionRegistry: versão duplicada {key!r} (sem override)."
            )

        if schema_version.parent_version is not None:
            parent_key = (
                f"{schema_version.contract_id}:{schema_version.parent_version}"
            )
            if parent_key not in self._versions:
                raise EvolutionRegistryError(
                    f"EvolutionRegistry: parent ausente {parent_key!r}."
                )

        existing = self._versions.get(key)
        if existing is not None and existing.hash != schema_version.hash:
            raise SchemaVersionDuplicateError(
                f"EvolutionRegistry: hash mismatch em {key!r}."
            )

        self._versions[key] = schema_version
        versions = self._by_contract.setdefault(schema_version.contract_id, [])
        if schema_version.version not in versions:
            versions.append(schema_version.version)
            versions.sort()

    def get_version(
        self,
        contract_id: str,
        version: str | None = None,
    ) -> SchemaVersion:
        if version is None:
            versions = self._by_contract.get(contract_id)
            if not versions:
                raise SchemaNotFoundError(
                    f"EvolutionRegistry: contract_id desconhecido {contract_id!r}."
                )
            version = versions[-1]

        key = f"{contract_id}:{version}"
        try:
            return self._versions[key]
        except KeyError as exc:
            raise SchemaNotFoundError(
                f"EvolutionRegistry: versão não encontrada {key!r}."
            ) from exc

    def list_versions(self, contract_id: str | None = None) -> list[SchemaVersion]:
        if contract_id is None:
            return sorted(
                self._versions.values(),
                key=lambda v: (v.contract_id, v.version),
            )
        return [
            self.get_version(contract_id, v)
            for v in self._by_contract.get(contract_id, [])
        ]

    def validate_chain_integrity(self) -> dict[str, Any]:
        """Valida grafo de versões (sem ciclos, parents válidos, hashes)."""
        errors: list[str] = []

        for key, version in self._versions.items():
            if version.registry_key != key:
                errors.append(f"{key}: registry_key inconsistente.")

            from src.evolution.schema_version import compute_schema_hash

            if compute_schema_hash(version.schema) != version.hash:
                errors.append(f"{key}: hash inconsistente.")

            if version.parent_version is None:
                continue

            parent_key = f"{version.contract_id}:{version.parent_version}"
            if parent_key not in self._versions:
                errors.append(f"{key}: parent ausente {parent_key!r}.")
                continue

            parent = self._versions[parent_key]
            if version.status == SchemaStatus.ACTIVE and parent.status == SchemaStatus.BLOCKED:
                errors.append(
                    f"{key}: filho active com parent blocked ({parent_key!r})."
                )

        active_counts: dict[str, int] = {}
        for version in self._versions.values():
            if version.status == SchemaStatus.ACTIVE:
                active_counts[version.contract_id] = (
                    active_counts.get(version.contract_id, 0) + 1
                )
        for contract_id, count in active_counts.items():
            if count > 1:
                errors.append(
                    f"{contract_id}: múltiplas versões active ({count})."
                )

        return {
            "valid": len(errors) == 0,
            "version_count": len(self._versions),
            "errors": sorted(errors),
        }


def bootstrap_pipeline_evolution_registry() -> EvolutionRegistry:
    """
    Bootstrap CI — registra v1 dos pipelines ativos no Contract Registry.
    """
    from microstructure.contracts.registry import CONTRACT_TYPES, contract_registry

    registry = EvolutionRegistry()
    for contract_type in CONTRACT_TYPES:
        contract = contract_registry.get_active_contract(contract_type)
        version_label = contract_registry.get_active_version(contract_type)
        sv = SchemaVersion.from_pipeline_contract(
            contract,
            contract_id=contract_type,
            version=version_label,
            parent_version=None,
            status=SchemaStatus.ACTIVE,
        )
        registry.register_version(sv)

    return registry


def validate_evolution_ci(registry: EvolutionRegistry | None = None) -> dict[str, Any]:
    """
    Gate CI — cadeia íntegra; breaking exige plano de migração registrável.
    """
    from src.evolution.migration_engine import MigrationEngine

    reg = registry or bootstrap_pipeline_evolution_registry()
    failures: list[str] = []

    chain_report = reg.validate_chain_integrity()
    if not chain_report["valid"]:
        failures.extend(chain_report["errors"])

    engine = MigrationEngine()
    from microstructure.contracts.registry import CONTRACT_TYPES

    for contract_id in CONTRACT_TYPES:
        versions = [v.version for v in reg.list_versions(contract_id)]
        for idx in range(1, len(versions)):
            v_from = versions[idx - 1]
            v_to = versions[idx]
            path_report = engine.validate_migration_path(
                reg, contract_id, v_from, v_to
            )
            if not path_report["valid"]:
                failures.extend(path_report["failures"])
            try:
                plan = engine.plan_migration(
                    reg.get_version(contract_id, v_from),
                    reg.get_version(contract_id, v_to),
                )
                if plan.breaking and not plan.steps:
                    failures.append(
                        f"{contract_id}:{v_from}->{v_to}: breaking sem migração."
                    )
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    f"{contract_id}:{v_from}->{v_to}: {exc}."
                )

    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }
