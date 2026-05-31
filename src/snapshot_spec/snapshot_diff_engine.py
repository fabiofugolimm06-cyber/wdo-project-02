"""
snapshot_diff_engine.py — diff estrutural e métrico entre specs.
"""

from __future__ import annotations

from typing import Any

from microstructure.contracts.snapshot import DEFAULT_NUMERIC_EPSILON
from src.snapshot_spec.snapshot_spec import SnapshotSpec


class SnapshotDiffEngine:
    """
    Diff entre ``SnapshotSpec`` — estrutura tem prioridade sobre métricas.

    Structural drift → ``breaking=True`` (FAIL CI).
    """

    def __init__(self, *, epsilon: float = DEFAULT_NUMERIC_EPSILON) -> None:
        self.epsilon = epsilon

    def diff(
        self,
        old_snapshot: SnapshotSpec,
        new_snapshot: SnapshotSpec,
    ) -> dict[str, Any]:
        changes: list[str] = []
        breaking = False

        if old_snapshot.contract_id != new_snapshot.contract_id:
            changes.append(
                f"contract_id:{old_snapshot.contract_id}->{new_snapshot.contract_id}"
            )
            breaking = True

        if old_snapshot.pipeline_stage != new_snapshot.pipeline_stage:
            changes.append(
                f"pipeline_stage:{old_snapshot.pipeline_stage}->"
                f"{new_snapshot.pipeline_stage}"
            )
            breaking = True

        structural = self.detect_structural_drift(old_snapshot, new_snapshot)
        changes.extend(structural["changes"])
        breaking = breaking or structural["breaking"]

        metric = self.detect_metric_drift(old_snapshot, new_snapshot)
        changes.extend(metric["changes"])
        if metric["breaking"]:
            breaking = True

        if old_snapshot.deterministic_seed != new_snapshot.deterministic_seed:
            changes.append(
                f"deterministic_seed:{old_snapshot.deterministic_seed}->"
                f"{new_snapshot.deterministic_seed}"
            )
            breaking = True

        if old_snapshot.state_hash != new_snapshot.state_hash and not breaking:
            changes.append(
                f"state_hash:{old_snapshot.state_hash}!={new_snapshot.state_hash}"
            )

        return {
            "breaking": breaking,
            "changes": sorted(set(changes)),
        }

    def detect_structural_drift(
        self,
        old_snapshot: SnapshotSpec,
        new_snapshot: SnapshotSpec,
    ) -> dict[str, Any]:
        """Schema + structure — igualdade estrita."""
        changes: list[str] = []

        if old_snapshot.structure != new_snapshot.structure:
            old_schema = old_snapshot.structure.get("schema")
            new_schema = new_snapshot.structure.get("schema")
            if old_schema != new_schema:
                changes.append("structural_drift:schema")
            old_body = old_snapshot.structure.get("structure")
            new_body = new_snapshot.structure.get("structure")
            if old_body != new_body:
                changes.append("structural_drift:structure")
            if not changes:
                changes.append("structural_drift:structure_root")

        return {
            "breaking": bool(changes),
            "changes": sorted(changes),
        }

    def detect_metric_drift(
        self,
        old_snapshot: SnapshotSpec,
        new_snapshot: SnapshotSpec,
        *,
        epsilon: float | None = None,
    ) -> dict[str, Any]:
        """Drift numérico com tolerância epsilon (não-breaking se dentro)."""
        eps = self.epsilon if epsilon is None else epsilon
        changes: list[str] = []
        breaking = False

        old_metrics = old_snapshot.metrics
        new_metrics = new_snapshot.metrics

        if set(old_metrics.keys()) != set(new_metrics.keys()):
            changes.append(
                f"metric_keys:{sorted(old_metrics)}!={sorted(new_metrics)}"
            )
            return {"breaking": True, "changes": sorted(changes)}

        for key in sorted(old_metrics.keys()):
            sub_changes, sub_breaking = self._compare_metric_block(
                old_metrics[key],
                new_metrics[key],
                prefix=key,
                epsilon=eps,
            )
            changes.extend(sub_changes)
            breaking = breaking or sub_breaking

        return {
            "breaking": breaking,
            "changes": sorted(changes),
        }

    @staticmethod
    def _compare_metric_block(
        old_block: Any,
        new_block: Any,
        *,
        prefix: str,
        epsilon: float,
    ) -> tuple[list[str], bool]:
        changes: list[str] = []
        breaking = False

        if isinstance(old_block, dict) and isinstance(new_block, dict):
            if set(old_block.keys()) != set(new_block.keys()):
                changes.append(f"{prefix}.keys_drift")
                return changes, True
            for key in sorted(old_block.keys()):
                sub_changes, sub_breaking = SnapshotDiffEngine._compare_metric_block(
                    old_block[key],
                    new_block[key],
                    prefix=f"{prefix}.{key}",
                    epsilon=epsilon,
                )
                changes.extend(sub_changes)
                breaking = breaking or sub_breaking
            return changes, breaking

        if isinstance(old_block, (int, float)) and isinstance(new_block, (int, float)):
            if abs(float(old_block) - float(new_block)) > epsilon:
                changes.append(
                    f"{prefix}:|{old_block}-{new_block}|>{epsilon}"
                )
            return changes, False

        if old_block != new_block:
            changes.append(f"{prefix}:{old_block!r}!={new_block!r}")
            breaking = True

        return changes, breaking
