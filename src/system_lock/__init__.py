"""System Lock Layer — freeze, mutation guard e paths protegidos."""

from src.system_lock.lock_registry import (
    ChangeProposal,
    FreezeRecord,
    LockRegistry,
    LockRegistryError,
    MutationRecord,
    bootstrap_production_lock_registry,
    validate_system_lock,
)
from src.system_lock.mutation_guard import MutationGuard
from src.system_lock.protected_paths import (
    PROTECTED_AREAS,
    ProtectedPathError,
    classify_path,
    is_protected_path,
    validate_modification_path,
)
from src.system_lock.system_freeze import SystemFreeze

__all__ = [
    "ChangeProposal",
    "FreezeRecord",
    "LockRegistry",
    "LockRegistryError",
    "MutationGuard",
    "MutationRecord",
    "PROTECTED_AREAS",
    "ProtectedPathError",
    "SystemFreeze",
    "bootstrap_production_lock_registry",
    "classify_path",
    "is_protected_path",
    "validate_modification_path",
    "validate_system_lock",
]
