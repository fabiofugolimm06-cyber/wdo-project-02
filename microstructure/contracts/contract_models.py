"""
microstructure/contracts/contract_models.py — modelo versionado de contratos de pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class NestedOutputSchema:
    """Schema de um bloco aninhado (ex.: ``metrics``, ``model_metrics``)."""

    block_name: str
    required_keys: frozenset[str]
    forbidden_keys: frozenset[str] = field(default_factory=frozenset)
    allow_extra_keys: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_name": self.block_name,
            "required_keys": sorted(self.required_keys),
            "forbidden_keys": sorted(self.forbidden_keys),
            "allow_extra_keys": self.allow_extra_keys,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NestedOutputSchema:
        return cls(
            block_name=str(data["block_name"]),
            required_keys=frozenset(data["required_keys"]),
            forbidden_keys=frozenset(data.get("forbidden_keys", [])),
            allow_extra_keys=bool(data.get("allow_extra_keys", False)),
        )


@dataclass(frozen=True)
class PipelineContract:
    """
    Contrato versionado de saída de pipeline.

    Attributes
    ----------
    contract_id : identificador estável (ex. ``ml_pipeline_contract_v1``).
    version : string de versão semver-like (ex. ``1.0.0``).
    output_schema : descrição legível do shape de saída (documentação + diff).
    required_top_keys : chaves obrigatórias no dict retornado.
    forbidden_top_keys : chaves proibidas no top-level.
    nested_schemas : blocos dict aninhados e suas regras.
    allow_extra_top_keys : se False, top-level deve ser exatamente required (+ nested).
    """

    contract_id: str
    version: str
    output_schema: dict[str, str]
    required_top_keys: frozenset[str]
    forbidden_top_keys: frozenset[str] = field(default_factory=frozenset)
    nested_schemas: tuple[NestedOutputSchema, ...] = ()
    allow_extra_top_keys: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "version": self.version,
            "output_schema": dict(self.output_schema),
            "required_top_keys": sorted(self.required_top_keys),
            "forbidden_top_keys": sorted(self.forbidden_top_keys),
            "nested_schemas": [n.to_dict() for n in self.nested_schemas],
            "allow_extra_top_keys": self.allow_extra_top_keys,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PipelineContract:
        nested = tuple(
            NestedOutputSchema.from_dict(n)
            for n in data.get("nested_schemas", [])
        )
        return cls(
            contract_id=str(data["contract_id"]),
            version=str(data["version"]),
            output_schema=dict(data["output_schema"]),
            required_top_keys=frozenset(data["required_top_keys"]),
            forbidden_top_keys=frozenset(data.get("forbidden_top_keys", [])),
            nested_schemas=nested,
            allow_extra_top_keys=bool(data.get("allow_extra_top_keys", False)),
        )

    def validate_output(self, output: Mapping[str, Any]) -> None:
        """Valida ``output`` contra este contrato (runtime guardrail)."""
        if not isinstance(output, Mapping):
            raise ValueError(
                f"{self.contract_id}: output deve ser mapping, got {type(output)!r}."
            )

        keys = frozenset(output.keys())

        forbidden_hit = keys & self.forbidden_top_keys
        if forbidden_hit:
            raise ValueError(
                f"{self.contract_id}: chaves top-level proibidas {sorted(forbidden_hit)}."
            )

        missing_top = self.required_top_keys - keys
        if missing_top:
            raise ValueError(
                f"{self.contract_id}: chaves top-level ausentes {sorted(missing_top)}."
            )

        if not self.allow_extra_top_keys:
            extra_top = keys - self.required_top_keys
            if extra_top:
                raise ValueError(
                    f"{self.contract_id}: chaves top-level não permitidas {sorted(extra_top)}."
                )

        for nested in self.nested_schemas:
            if nested.block_name not in output:
                raise ValueError(
                    f"{self.contract_id}: bloco '{nested.block_name}' ausente."
                )
            block = output[nested.block_name]
            if not isinstance(block, Mapping):
                raise ValueError(
                    f"{self.contract_id}: '{nested.block_name}' deve ser mapping."
                )
            block_keys = frozenset(block.keys())

            forbidden_nested = block_keys & nested.forbidden_keys
            if forbidden_nested:
                raise ValueError(
                    f"{self.contract_id}: '{nested.block_name}' contém chaves "
                    f"proibidas {sorted(forbidden_nested)}."
                )

            missing_nested = nested.required_keys - block_keys
            if missing_nested:
                raise ValueError(
                    f"{self.contract_id}: '{nested.block_name}' incompleto, "
                    f"ausentes {sorted(missing_nested)}."
                )

            if not nested.allow_extra_keys:
                extra_nested = block_keys - nested.required_keys
                if extra_nested:
                    raise ValueError(
                        f"{self.contract_id}: '{nested.block_name}' chaves extras "
                        f"{sorted(extra_nested)}."
                    )

            for key in nested.required_keys:
                val = block[key]
                if isinstance(val, (int, float)) and val != val:
                    raise ValueError(
                        f"{self.contract_id}: '{nested.block_name}.{key}' é NaN."
                    )
