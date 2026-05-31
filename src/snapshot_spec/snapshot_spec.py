"""
snapshot_spec.py — entidade imutável de spec oficial (Snapshot-as-Spec).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from microstructure.contracts.snapshot import DEFAULT_NUMERIC_EPSILON


class SnapshotSpecError(Exception):
    """Erro base do Snapshot-as-Spec engine."""


class PipelineStage(str, Enum):
    ML = "ml"
    FULL = "full"
    E2E = "e2e"


def compute_state_hash(
    *,
    contract_id: str,
    pipeline_stage: str,
    structure: Mapping[str, Any],
    metrics: Mapping[str, Any],
    deterministic_seed: int,
) -> str:
    """SHA256 determinístico do conteúdo canônico da spec (sem snapshot_id)."""
    payload = json.dumps(
        {
            "contract_id": contract_id,
            "pipeline_stage": pipeline_stage,
            "structure": dict(structure),
            "metrics": dict(metrics),
            "deterministic_seed": int(deterministic_seed),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_structure(raw: Mapping[str, Any]) -> dict[str, Any]:
    if "schema" not in raw or "structure" not in raw:
        raise SnapshotSpecError("snapshot raw deve conter schema e structure.")
    return {
        "schema": dict(raw["schema"]),
        "structure": dict(raw["structure"]),
    }


def _extract_metrics(raw: Mapping[str, Any]) -> dict[str, Any]:
    if "metrics" in raw:
        return {k: _normalize_metric_value(v) for k, v in raw["metrics"].items()}
    metrics: dict[str, Any] = {}
    for block in ("model_metrics", "execution_metrics", "backtest_metrics"):
        if block in raw:
            block_data = raw[block]
            if not isinstance(block_data, Mapping):
                raise SnapshotSpecError(f"{block} deve ser mapping.")
            metrics[block] = {
                k: _normalize_metric_value(v) for k, v in block_data.items()
            }
    if not metrics:
        raise SnapshotSpecError("snapshot raw sem blocos de métricas conhecidos.")
    return metrics


def _normalize_metric_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 12)
    if isinstance(value, list):
        return [_normalize_metric_value(v) for v in value]
    return value


def _normalize_pipeline_stage(stage: str) -> str:
    normalized = stage.strip().lower()
    if normalized == "e2e":
        return PipelineStage.FULL.value
    if normalized not in {PipelineStage.ML.value, PipelineStage.FULL.value}:
        raise SnapshotSpecError(f"pipeline_stage inválido: {stage!r}.")
    return normalized


@dataclass(frozen=True)
class SnapshotSpec:
    """
    Spec oficial imutável de um snapshot de pipeline.

    ``state_hash`` reflete conteúdo canônico (structure + metrics + seed).
    """

    snapshot_id: str
    contract_id: str
    pipeline_stage: str
    state_hash: str
    structure: dict[str, Any]
    metrics: dict[str, Any]
    deterministic_seed: int

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip():
            raise SnapshotSpecError("snapshot_id vazio.")
        if not self.contract_id.strip():
            raise SnapshotSpecError("contract_id vazio.")
        stage = _normalize_pipeline_stage(self.pipeline_stage)
        object.__setattr__(self, "pipeline_stage", stage)
        expected = compute_state_hash(
            contract_id=self.contract_id,
            pipeline_stage=stage,
            structure=self.structure,
            metrics=self.metrics,
            deterministic_seed=self.deterministic_seed,
        )
        if self.state_hash != expected:
            raise SnapshotSpecError(
                "state_hash inconsistente com conteúdo da spec."
            )

    @classmethod
    def from_raw_snapshot(
        cls,
        raw: Mapping[str, Any],
        *,
        snapshot_id: str,
        pipeline_stage: str,
        deterministic_seed: int,
    ) -> SnapshotSpec:
        """Constrói spec a partir de snapshot JSON de pipeline."""
        contract_id = str(raw.get("contract_id", ""))
        if not contract_id:
            raise SnapshotSpecError("contract_id ausente no snapshot raw.")
        structure = _extract_structure(raw)
        metrics = _extract_metrics(raw)
        stage = _normalize_pipeline_stage(pipeline_stage)
        state_hash = compute_state_hash(
            contract_id=contract_id,
            pipeline_stage=stage,
            structure=structure,
            metrics=metrics,
            deterministic_seed=deterministic_seed,
        )
        return cls(
            snapshot_id=snapshot_id,
            contract_id=contract_id,
            pipeline_stage=stage,
            state_hash=state_hash,
            structure=structure,
            metrics=metrics,
            deterministic_seed=int(deterministic_seed),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "contract_id": self.contract_id,
            "pipeline_stage": self.pipeline_stage,
            "state_hash": self.state_hash,
            "structure": dict(self.structure),
            "metrics": dict(self.metrics),
            "deterministic_seed": self.deterministic_seed,
        }


DEFAULT_SNAPSHOT_EPSILON = DEFAULT_NUMERIC_EPSILON
