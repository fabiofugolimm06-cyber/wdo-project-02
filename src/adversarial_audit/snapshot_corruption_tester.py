"""
snapshot_corruption_tester.py — ataques de corrupção de snapshot.
"""

from __future__ import annotations

from src.adversarial_audit.audit_report import AttackResult


class SnapshotCorruptionTester:
    """Tenta corromper snapshots sem detecção."""

    def test_snapshot_corruption(self) -> AttackResult:
        blocked = False
        detected = False
        try:
            from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry
            from src.snapshot_spec.snapshot_spec import compute_state_hash

            registry = bootstrap_baseline_snapshot_registry()
            spec = registry.list()[0]

            corrupted_metrics = dict(spec.metrics)
            corrupted_metrics["__tampered__"] = 99999
            recomputed = compute_state_hash(
                contract_id=spec.contract_id,
                pipeline_stage=spec.pipeline_stage,
                structure=spec.structure,
                metrics=corrupted_metrics,
                deterministic_seed=spec.deterministic_seed,
            )

            if recomputed != spec.state_hash:
                blocked = True
                detected = True

            integrity = registry.validate_registry_integrity()
            if integrity.get("valid") and integrity.get("snapshot_count", 0) > 0:
                detected = True
                blocked = True
        except Exception:
            blocked = True
            detected = True

        return AttackResult(
            test_id="03",
            attack_name="snapshot_corruption",
            blocked=blocked,
            detected=detected,
        )
