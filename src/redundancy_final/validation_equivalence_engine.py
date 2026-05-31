"""
validation_equivalence_engine.py — equivalência comportamental before/after.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.redundancy_final.system_overlap_analyzer import CONSOLIDATED_COVERAGE


def _behavioral_payload(reports: dict[str, dict[str, Any]]) -> str:
    slim = {
        gate: {
            "status": report.get("status"),
            "failures": sorted(report.get("failures", [])),
        }
        for gate, report in sorted(reports.items())
    }
    return json.dumps(slim, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_behavioral_fingerprint(
    reports: dict[str, dict[str, Any]],
) -> str:
    return hashlib.sha256(_behavioral_payload(reports).encode("utf-8")).hexdigest()


class ValidationEquivalenceEngine:
    """Verifica identidade comportamental entre pipelines."""

    def verify_system_equivalence(
        self,
        before: dict[str, dict[str, Any]],
        after: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failures: list[str] = []
        fp_before = compute_behavioral_fingerprint(before)
        fp_after = compute_behavioral_fingerprint(after)

        if fp_before != fp_after:
            failures.append(
                f"equivalence: fingerprint diverge "
                f"({fp_before[:12]}… != {fp_after[:12]}…)."
            )

        for gate, status_before in sorted(
            (g, r.get("status")) for g, r in before.items()
        ):
            status_after = after.get(gate, {}).get("status", "MISSING")
            if status_before != status_after:
                failures.append(
                    f"equivalence:{gate}: {status_before}->{status_after}."
                )

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "fingerprint_before": fp_before,
            "fingerprint_after": fp_after,
            "equivalent": not ordered,
        }

    def enforce_behavioral_identity(
        self,
        reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        fp_a = compute_behavioral_fingerprint(reports)
        fp_b = compute_behavioral_fingerprint(reports)
        failures: list[str] = []
        if fp_a != fp_b:
            failures.append("identity: fingerprint instável em recompute.")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "behavioral_fingerprint": fp_a,
            "deterministic": fp_a == fp_b,
        }

    def project_consolidated_to_legacy(
        self,
        consolidated_reports: dict[str, dict[str, Any]],
        legacy_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Legacy reports expandidos devem cobrir toda cobertura consolidada."""
        failures: list[str] = []
        for merged_gate, legacy_gates in sorted(CONSOLIDATED_COVERAGE.items()):
            if merged_gate not in consolidated_reports:
                failures.append(f"coverage: {merged_gate} ausente.")
                continue
            if consolidated_reports[merged_gate].get("status") == "PASS":
                for legacy_gate in legacy_gates:
                    if legacy_reports.get(legacy_gate, {}).get("status") != "PASS":
                        failures.append(f"coverage:{legacy_gate}: não PASS.")

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "legacy_gate_count": len(legacy_reports),
        }
