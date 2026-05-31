"""
artifact_builder.py — constrói artefato oficial da release.
"""

from __future__ import annotations

from typing import Any

from src.certification.system_certificate import WDO_RELEASE_NAME, WDO_SYSTEM_VERSION


class ArtifactBuilder:
    """Monta conteúdo do bundle WDO_PROJECT_02_v1.0.0."""

    def build_artifact(
        self,
        *,
        manifest: dict[str, Any],
        certificate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

        registry = bootstrap_baseline_snapshot_registry()
        snapshots = [
            {
                "snapshot_id": spec.snapshot_id,
                "state_hash": spec.state_hash,
                "pipeline_stage": spec.pipeline_stage,
            }
            for spec in registry.list()
        ]

        from src.config.config_registry import build_canonical_config_schema

        config_schema = build_canonical_config_schema()

        cert = certificate or {}
        return {
            "name": WDO_RELEASE_NAME,
            "version": WDO_SYSTEM_VERSION,
            "contracts": {"fingerprint": manifest.get("contracts_fingerprint", "")},
            "snapshots": snapshots,
            "registries": {
                "snapshot_count": len(snapshots),
                "contract_registry": "microstructure.contracts.registry",
            },
            "configs": config_schema,
            "fingerprints": {
                "data": manifest.get("data_fingerprint", ""),
                "system": manifest.get("system_fingerprint", ""),
            },
            "certificates": cert,
            "manifest": manifest,
        }
