"""
system_surface.py — superfície pública mínima do sistema.
"""

from __future__ import annotations

from typing import Any

# APIs públicas canônicas (import preferencial).
_PUBLIC_INTERFACES: dict[str, tuple[str, ...]] = {
    "contracts": (
        "microstructure.contracts.get_contract",
        "microstructure.contracts.contract_registry",
    ),
    "data": (
        "src.contracts.data.DataContract",
        "src.contracts.data.DatasetRegistry",
    ),
    "evolution": (
        "src.evolution.get_contract",
        "src.evolution.validate_evolution_ci",
    ),
    "snapshot_spec": (
        "src.snapshot_spec.SnapshotCIGate",
        "src.snapshot_spec.bootstrap_baseline_snapshot_registry",
    ),
    "ci": (
        "src.ci.ContractCIGate",
        "src.ci.DataCIGate",
        "scripts.run_architecture_gate.run_architecture_gate",
    ),
    "observability": (
        "src.observability.SystemFingerprintLogger",
        "src.observability.RunLogger",
    ),
    "health": (
        "src.health.SystemHealthMonitor",
    ),
    "system_lock": (
        "src.system_lock.validate_system_lock",
    ),
    "config": (
        "src.config.run_config_freeze_gate",
    ),
    "consolidation": (
        "src.consolidation.run_consolidation_gate",
    ),
}

_INTERNAL_PREFIXES: tuple[str, ...] = (
    "src.ci.final_gates",
    "src.watchdog.pipeline_monitor",
    "src.prod_lock.runtime_guard",
    "src.simplification",
    "src.ci_optimizer",
    "src.invariants.invariant_registry",
)


class SystemSurface:
    """Expõe superfície mínima vs interna."""

    def list_public_interfaces(self) -> dict[str, tuple[str, ...]]:
        return dict(_PUBLIC_INTERFACES)

    def list_internal_interfaces(self) -> tuple[str, ...]:
        return _INTERNAL_PREFIXES

    def expose_minimal_api_surface(self) -> dict[str, Any]:
        public = self.list_public_interfaces()
        flat_public = sorted(
            api for apis in public.values() for api in apis
        )
        return {
            "public_modules": sorted(public.keys()),
            "public_apis": flat_public,
            "public_api_count": len(flat_public),
            "internal_prefixes": list(self.list_internal_interfaces()),
            "internal_prefix_count": len(_INTERNAL_PREFIXES),
        }
