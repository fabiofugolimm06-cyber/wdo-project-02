"""
adversarial_ci_gate.py — gate CI oficial da auditoria adversarial independente.
"""

from __future__ import annotations

from typing import Any

from src.adversarial_audit.audit_report import (
    AdversarialAuditReport,
    AttackResult,
    _hash_results,
    run_adversarial_audit,
)

REQUIRED_ATTACKS: tuple[tuple[str, str], ...] = (
    ("01", "contract_tampering"),
    ("02", "registry_overwrite_attack"),
    ("03", "snapshot_corruption"),
    ("04", "evolution_chain_corruption"),
    ("05", "runtime_mutation_attack"),
    ("06", "config_mutation_attack"),
    ("07", "release_artifact_modification"),
    ("08", "rollback_poisoning"),
    ("09", "fingerprint_collision_simulation"),
    ("10", "recovery_failure_simulation"),
)

REQUIRED_ATTACK_COUNT = len(REQUIRED_ATTACKS)


class AdversarialAuditGate:
    """Gate oficial — 10 ataques simulados, zero vulnerabilidades silenciosas."""

    def validate_attack_coverage(self, report: AdversarialAuditReport) -> list[str]:
        failures: list[str] = []
        if report.tests_executed != REQUIRED_ATTACK_COUNT:
            failures.append(
                f"adversarial: attacks_executed={report.tests_executed} "
                f"(esperado {REQUIRED_ATTACK_COUNT})."
            )

        executed = {(item["test_id"], item["attack_name"]) for item in report.results}
        for test_id, attack_name in REQUIRED_ATTACKS:
            if (test_id, attack_name) not in executed:
                failures.append(
                    f"adversarial: ataque obrigatório ausente {test_id}:{attack_name}."
                )
        return failures

    def validate_zero_undetected_vulnerabilities(
        self,
        report: AdversarialAuditReport,
    ) -> list[str]:
        failures: list[str] = []
        if report.vulnerabilities_found != 0:
            failures.append(
                f"adversarial: vulnerabilities_found={report.vulnerabilities_found}."
            )
        for item in report.results:
            if item.get("vulnerability"):
                failures.append(
                    f"adversarial: vulnerabilidade não detectada "
                    f"{item['test_id']}:{item['attack_name']}."
                )
        return failures

    def _validate_audit_hash(self, report: AdversarialAuditReport) -> list[str]:
        results = [
            AttackResult(
                test_id=item["test_id"],
                attack_name=item["attack_name"],
                blocked=item["blocked"],
                detected=item["detected"],
            )
            for item in report.results
        ]
        expected = _hash_results(results)
        if expected != report.audit_hash:
            return ["adversarial: audit_hash inconsistente."]
        return []

    def _validate_pass_criteria(self, report: AdversarialAuditReport) -> list[str]:
        failures: list[str] = []
        if report.tests_executed != REQUIRED_ATTACK_COUNT:
            failures.append("adversarial: attacks_executed != 10.")
        if report.attacks_detected != REQUIRED_ATTACK_COUNT:
            failures.append(
                f"adversarial: attacks_detected={report.attacks_detected} (esperado 10)."
            )
        if report.vulnerabilities_found != 0:
            failures.append("adversarial: vulnerabilities_found != 0.")
        return failures

    def _finalize_certificate(
        self,
        *,
        report: AdversarialAuditReport,
        gate_reports: dict[str, dict[str, Any]],
        gate_pass: bool,
    ) -> dict[str, Any]:
        from src.certification.system_certificate import CertificateRegistry

        architecture_pass = (
            gate_reports.get("certification-gate", {}).get("status") == "PASS"
        )
        long_run_pass = (
            gate_reports.get("long-run-validation-gate", {}).get("status") == "PASS"
        )
        release_pass = (
            gate_reports.get("release-packaging-gate", {}).get("status") == "PASS"
        )
        adversarial_pass = gate_pass

        return CertificateRegistry.finalize_adversarial_audit(
            adversarial_audit_hash=report.audit_hash,
            adversarial_audit_status="PASS" if gate_pass else "FAIL",
            architecture_pass=architecture_pass,
            long_run_pass=long_run_pass,
            release_pass=release_pass,
            adversarial_pass=adversarial_pass,
        )

    def run_adversarial_audit_gate(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Executa adversarial-audit-gate — gate #17 do pipeline v10."""
        report = run_adversarial_audit()
        failures: list[str] = []
        failures.extend(self._validate_audit_hash(report))
        failures.extend(self.validate_attack_coverage(report))
        failures.extend(self.validate_zero_undetected_vulnerabilities(report))
        failures.extend(self._validate_pass_criteria(report))

        gate_pass = not failures and report.status == "PASS"
        certificate_finalize: dict[str, Any] | None = None

        if gate_reports is not None:
            finalize = self._finalize_certificate(
                report=report,
                gate_reports=gate_reports,
                gate_pass=gate_pass,
            )
            certificate_finalize = finalize
            if finalize["status"] != "PASS":
                failures.extend(finalize.get("failures", []))

        ordered = sorted(set(failures))
        status = "PASS" if not ordered else "FAIL"

        return {
            "status": status,
            "failures": ordered,
            "audit_hash": report.audit_hash,
            "attacks_executed": report.tests_executed,
            "attacks_blocked": report.attacks_blocked,
            "attacks_detected": report.attacks_detected,
            "vulnerabilities_found": report.vulnerabilities_found,
            "attack_coverage": REQUIRED_ATTACK_COUNT,
            "certificate_finalize": certificate_finalize,
            "report": report.to_dict(),
        }


def run_adversarial_audit_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Atalho CI — adversarial-audit-gate."""
    return AdversarialAuditGate().run_adversarial_audit_gate(gate_reports=gate_reports)
