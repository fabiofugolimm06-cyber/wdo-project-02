"""Evolution Rule Engine — versionamento protobuf-like de schemas."""

from src.evolution.breaking_change_detector import (
    detect_contract_breaking_changes,
    detect_removed_fields,
    detect_type_changes,
)
from src.evolution.evolution_registry import (
    EvolutionRegistry,
    EvolutionRegistryError,
    SchemaNotFoundError,
    SchemaVersionDuplicateError,
    bootstrap_pipeline_evolution_registry,
    validate_evolution_ci,
)
from src.evolution.migration_engine import (
    MigrationEngine,
    MigrationError,
    MigrationPlan,
    MigrationStep,
)
from src.evolution.schema_version import (
    SchemaStatus,
    SchemaVersion,
    SchemaVersionError,
    compute_schema_hash,
)

__all__ = [
    "EvolutionRegistry",
    "EvolutionRegistryError",
    "MigrationEngine",
    "MigrationError",
    "MigrationPlan",
    "MigrationStep",
    "SchemaNotFoundError",
    "SchemaStatus",
    "SchemaVersion",
    "SchemaVersionDuplicateError",
    "SchemaVersionError",
    "bootstrap_pipeline_evolution_registry",
    "compute_schema_hash",
    "detect_contract_breaking_changes",
    "detect_removed_fields",
    "detect_type_changes",
    "validate_evolution_ci",
]
