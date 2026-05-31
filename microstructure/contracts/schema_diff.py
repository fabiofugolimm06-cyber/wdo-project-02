"""
microstructure/contracts/schema_diff.py — diff entre contratos versionados.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from microstructure.contracts.contract_models import NestedOutputSchema, PipelineContract


@dataclass(frozen=True)
class ContractDiffResult:
    added_keys: frozenset[str]
    removed_keys: frozenset[str]
    modified_constraints: tuple[str, ...]
    breaking_changes: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "added_keys": sorted(self.added_keys),
            "removed_keys": sorted(self.removed_keys),
            "modified_constraints": list(self.modified_constraints),
            "breaking_changes": self.breaking_changes,
        }


def _nested_by_name(
    contract: PipelineContract,
) -> dict[str, NestedOutputSchema]:
    return {n.block_name: n for n in contract.nested_schemas}


def diff_contracts(v1: PipelineContract, v2: PipelineContract) -> ContractDiffResult:
    """
    Compara dois contratos e classifica mudanças estruturais.

    Breaking (CI deve falhar):
    - remoção de required_top_keys
    - remoção de bloco nested ou de required_keys em nested
    - ``allow_extra_*`` passa de True → False (restringe saída)
    - remoção de entrada em ``output_schema`` documentada
    - ``forbidden_keys`` reduzidas no nested ML (permite métricas de backtest)
    """
    added_keys: set[str] = set()
    removed_keys: set[str] = set()
    modified: list[str] = []

    removed_top = v1.required_top_keys - v2.required_top_keys
    if removed_top:
        removed_keys.update(removed_top)
        modified.append(f"required_top_keys removidas: {sorted(removed_top)}")

    added_top = v2.required_top_keys - v1.required_top_keys
    if added_top:
        added_keys.update(added_top)
        modified.append(f"required_top_keys adicionadas: {sorted(added_top)}")

    relaxed_forbidden_top = v1.forbidden_top_keys - v2.forbidden_top_keys
    if relaxed_forbidden_top:
        modified.append(
            f"forbidden_top_keys relaxadas: {sorted(relaxed_forbidden_top)}"
        )

    if v1.allow_extra_top_keys and not v2.allow_extra_top_keys:
        modified.append("allow_extra_top_keys: True → False")

    schema_v1 = frozenset(v1.output_schema.keys())
    schema_v2 = frozenset(v2.output_schema.keys())
    removed_schema = schema_v1 - schema_v2
    added_schema = schema_v2 - schema_v1
    if removed_schema:
        removed_keys.update(removed_schema)
        modified.append(f"output_schema removido: {sorted(removed_schema)}")
    if added_schema:
        added_keys.update(added_schema)
        modified.append(f"output_schema adicionado: {sorted(added_schema)}")

    nested_v1 = _nested_by_name(v1)
    nested_v2 = _nested_by_name(v2)

    for name in nested_v1:
        if name not in nested_v2:
            removed_keys.add(name)
            modified.append(f"nested block removido: {name}")

    for name, n2 in nested_v2.items():
        if name not in nested_v1:
            added_keys.add(name)
            modified.append(f"nested block adicionado: {name}")
            continue

        n1 = nested_v1[name]
        rem_req = n1.required_keys - n2.required_keys
        if rem_req:
            removed_keys.update(f"{name}.{k}" for k in rem_req)
            modified.append(f"{name}.required_keys removidas: {sorted(rem_req)}")

        add_req = n2.required_keys - n1.required_keys
        if add_req:
            added_keys.update(f"{name}.{k}" for k in add_req)
            modified.append(f"{name}.required_keys adicionadas: {sorted(add_req)}")

        relaxed_forbidden = n1.forbidden_keys - n2.forbidden_keys
        if relaxed_forbidden:
            modified.append(
                f"{name}.forbidden_keys relaxadas: {sorted(relaxed_forbidden)}"
            )

        if n1.allow_extra_keys and not n2.allow_extra_keys:
            modified.append(f"{name}.allow_extra_keys: True → False")

    breaking = bool(
        removed_keys
        or any("removidas" in m for m in modified)
        or any("removido" in m for m in modified)
        or any("True → False" in m for m in modified)
        or any("forbidden_keys relaxadas" in m for m in modified)
    )

    return ContractDiffResult(
        added_keys=frozenset(added_keys),
        removed_keys=frozenset(removed_keys),
        modified_constraints=tuple(modified),
        breaking_changes=breaking,
    )
