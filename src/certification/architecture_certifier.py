"""
architecture_certifier.py — certificação formal de integridade arquitetural.
"""

from __future__ import annotations

from typing import Any


class ArchitectureCertifier:
    """Certifica camadas arquiteturais individualmente."""

    def certify_contract_layer(self) -> dict[str, Any]:
        from src.ci import ContractCIGate

        report = ContractCIGate().run_full_contract_check()
        return {
            "layer": "contracts",
            "status": report.get("status", "FAIL"),
            "failures": report.get("failures", []),
        }

    def certify_evolution_layer(self) -> dict[str, Any]:
        from src.evolution.evolution_registry import validate_evolution_ci

        report = validate_evolution_ci()
        return {
            "layer": "evolution",
            "status": report.get("status", "FAIL"),
            "failures": report.get("failures", []),
        }

    def certify_snapshot_layer(self) -> dict[str, Any]:
        from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

        registry = bootstrap_baseline_snapshot_registry()
        integrity = registry.validate_registry_integrity()
        failures = list(integrity.get("errors", []))
        if integrity.get("snapshot_count", 0) < 1:
            failures.append("snapshot: baseline ausente.")
        ordered = sorted(set(failures))
        return {
            "layer": "snapshot_spec",
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "snapshot_count": integrity.get("snapshot_count", 0),
        }

    def certify_runtime_layer(self) -> dict[str, Any]:
        from src.simplification.dependency_map import DependencyMap

        dep = DependencyMap().validate_unidirectional()
        failures = list(dep.get("failures", []))
        ordered = sorted(set(failures))
        return {
            "layer": "runtime",
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
        }

    def certify_all(self) -> dict[str, Any]:
        layers = [
            self.certify_contract_layer(),
            self.certify_evolution_layer(),
            self.certify_snapshot_layer(),
            self.certify_runtime_layer(),
        ]
        failures: list[str] = []
        for layer in layers:
            if layer["status"] != "PASS":
                failures.extend(
                    f"{layer['layer']}:{msg}" for msg in layer.get("failures", [])
                )
        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "layers": layers,
        }
