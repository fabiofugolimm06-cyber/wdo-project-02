"""Snapshot-as-Spec Engine — spec oficial versionada do sistema."""

from src.snapshot_spec.snapshot_ci_gate import SnapshotCIGate
from src.snapshot_spec.snapshot_diff_engine import SnapshotDiffEngine
from src.snapshot_spec.snapshot_registry import (
    SnapshotDuplicateError,
    SnapshotNotFoundError,
    SnapshotRegistry,
    SnapshotRegistryError,
    bootstrap_baseline_snapshot_registry,
)
from src.snapshot_spec.snapshot_spec import (
    PipelineStage,
    SnapshotSpec,
    SnapshotSpecError,
    compute_state_hash,
)
from src.snapshot_spec.snapshot_validator import SnapshotValidator

__all__ = [
    "PipelineStage",
    "SnapshotCIGate",
    "SnapshotDiffEngine",
    "SnapshotDuplicateError",
    "SnapshotNotFoundError",
    "SnapshotRegistry",
    "SnapshotRegistryError",
    "SnapshotSpec",
    "SnapshotSpecError",
    "SnapshotValidator",
    "bootstrap_baseline_snapshot_registry",
    "compute_state_hash",
]
