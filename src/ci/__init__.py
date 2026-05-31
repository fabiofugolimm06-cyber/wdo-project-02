"""CI Engine — gates de arquitetura, contratos e determinismo."""

from src.ci.contract_ci_gate import ContractCIGate
from src.ci.data_ci_gate import DataCIGate, build_canonical_dataset_registry
from src.ci.snapshot_ci_gate import SnapshotCIGate

__all__ = [
    "ContractCIGate",
    "DataCIGate",
    "SnapshotCIGate",
    "build_canonical_dataset_registry",
]
