"""Config Freeze Layer — contratos de config versionados e imutáveis."""

from src.config.config_contract import (
    WDO_ACTIVE_CONFIG_ID,
    ConfigContract,
    ConfigContractError,
    build_canonical_config_schema,
    compute_config_hash,
)
from src.config.config_freeze_engine import ConfigFreezeEngine, run_config_freeze_gate
from src.config.config_registry import (
    ConfigDuplicateError,
    ConfigNotFoundError,
    ConfigRegistry,
    ConfigRegistryError,
    bootstrap_production_config_registry,
)
from src.config.config_validator import ConfigValidator

__all__ = [
    "WDO_ACTIVE_CONFIG_ID",
    "ConfigContract",
    "ConfigContractError",
    "ConfigDuplicateError",
    "ConfigFreezeEngine",
    "ConfigNotFoundError",
    "ConfigRegistry",
    "ConfigRegistryError",
    "ConfigValidator",
    "bootstrap_production_config_registry",
    "build_canonical_config_schema",
    "compute_config_hash",
    "run_config_freeze_gate",
]
