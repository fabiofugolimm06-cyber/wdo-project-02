"""
final_gates.py — gates finais do pipeline CI (audit, observability, health, lock).
"""

from __future__ import annotations

from typing import Any

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED


def _report(failures: list[str], **extra: Any) -> dict[str, Any]:
    ordered = sorted(failures)
    out: dict[str, Any] = {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }
    out.update(extra)
    return out


def run_audit_enforcement_gate() -> dict[str, Any]:
    """audit-enforcement-gate — trilha de auditoria determinística."""
    from src.observability import AuditEventBus, AuditEventType

    payload = {"seed": WDO_PROJECT_RANDOM_SEED, "gate": "audit-enforcement"}
    required = (
        AuditEventType.CONTRACT_REGISTERED,
        AuditEventType.DATASET_REGISTERED,
        AuditEventType.SNAPSHOT_CREATED,
        AuditEventType.CI_GATE_PASSED,
    )

    buses = [AuditEventBus(), AuditEventBus()]
    hashes: list[str] = []
    for bus in buses:
        for event_type in required:
            bus.emit(event_type, payload)
        hashes.append(bus.event_log_hash())

    failures: list[str] = []
    if hashes[0] != hashes[1]:
        failures.append("audit: event_log_hash não determinístico.")
    if len(set(hashes)) != 1:
        failures.append("audit: hashes divergentes entre runs.")

    return _report(failures, event_log_hash=hashes[0] if hashes else None)


def run_observability_fingerprint_gate() -> dict[str, Any]:
    """observability-fingerprint-gate — fingerprint global estável."""
    from src.observability import SystemFingerprintLogger

    logger = SystemFingerprintLogger()
    fp_a = logger.compute_system_fingerprint()
    fp_b = SystemFingerprintLogger().compute_system_fingerprint()
    state = logger.log_global_state()

    failures: list[str] = []
    if fp_a != fp_b:
        failures.append(
            f"observability: system_fingerprint instável ({fp_a[:12]}… != {fp_b[:12]}…)."
        )
    if len(state.get("system_fingerprint", "")) != 64:
        failures.append("observability: system_fingerprint inválido.")

    return _report(failures, system_fingerprint=fp_a)


def run_system_lock_gate() -> dict[str, Any]:
    """system-lock-gate — freeze + mutation guard."""
    from src.system_lock import validate_system_lock

    return validate_system_lock()


def run_error_taxonomy_gate(
    gate_reports: dict[str, dict[str, Any]],
    *,
    run_id: str = "pipeline-run",
) -> dict[str, Any]:
    """error-taxonomy-gate — falhas estruturais rastreáveis."""
    from src.errors import ErrorClassifier, ErrorType, FailureRegistry

    failures: list[str] = []
    classifier = ErrorClassifier()
    registry = FailureRegistry()

    for gate, report in sorted(gate_reports.items()):
        if report.get("status") == "FAIL":
            for classified in classifier.classify_gate_failures({gate: report}):
                registry.register_failure(classified, gate=gate, run_id=run_id)

    prior_failures = [
        gate
        for gate, report in gate_reports.items()
        if report.get("status") == "FAIL"
    ]
    if prior_failures:
        failures.append(
            f"taxonomy: gates anteriores falharam: {sorted(prior_failures)}."
        )

    for etype in ErrorType:
        if etype == ErrorType.UNKNOWN:
            continue
        probe_messages = {
            ErrorType.CONTRACT_VIOLATION: "contract violation",
            ErrorType.DATA_DRIFT: "dataset drift",
            ErrorType.SNAPSHOT_MISMATCH: "snapshot mismatch",
            ErrorType.EVOLUTION_BREAKING: "evolution breaking",
            ErrorType.CI_FAILURE: "ci gate failure",
            ErrorType.SYSTEM_LOCK_VIOLATION: "system lock freeze",
            ErrorType.CONFIG_DRIFT: "config drift",
            ErrorType.RUNTIME_MUTATION: "runtime prod mutation",
        }
        sample = classifier.classify_error(
            probe_messages.get(etype, etype.value),
            origin="error-taxonomy-gate",
        )
        if sample.error_type != etype:
            failures.append(f"taxonomy: classificador não mapeia {etype.value}.")

    if registry.compute_failure_rate()["total"] > 0 and not prior_failures:
        failures.append("taxonomy: failure registry inconsistente.")

    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "failure_count": len(registry.get_failure_history()),
    }
