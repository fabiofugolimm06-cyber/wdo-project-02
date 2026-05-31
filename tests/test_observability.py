"""
tests/test_observability.py — observabilidade determinística v1.
"""

from __future__ import annotations

from src.observability import (
    ArchitectureTrace,
    AuditEventBus,
    AuditEventType,
    RunLogger,
    SystemFingerprintLogger,
    derive_step_timestamp,
)


class TestRunLogger:
    def test_deterministic_run_hash(self):
        logger_a = RunLogger()
        logger_b = RunLogger()

        ctx = {"run_label": "architecture-gate-v1", "seed": 42}
        logger_a.log_run(ctx)
        logger_b.log_run(ctx)

        logger_a.log_step("contracts", {"status": "PASS"})
        logger_b.log_step("contracts", {"status": "PASS"})
        logger_a.finalize_run("PASS")
        logger_b.finalize_run("PASS")

        assert logger_a.run_hash == logger_b.run_hash
        assert len(logger_a.run_hash) == 64

    def test_derived_timestamps_no_real_clock(self):
        assert derive_step_timestamp(0) == "2000-01-01T00:00:00Z#step-0000"
        assert derive_step_timestamp(3) == "2000-01-01T00:00:00Z#step-0003"

    def test_steps_are_hashable(self):
        logger = RunLogger()
        logger.log_run({"seed": 42})
        step = logger.log_step("data", {"status": "PASS", "failures": []})
        assert "step_hash" in step
        assert len(step["step_hash"]) == 64


class TestArchitectureTrace:
    def test_trace_contract_flow_ml(self):
        graph = ArchitectureTrace().trace_contract_flow("ml_pipeline:v1")
        assert "nodes" in graph
        assert "edges" in graph
        assert all({"node", "dependency", "output"} <= set(e.keys()) for e in graph["edges"])

    def test_trace_data_flow(self):
        graph = ArchitectureTrace().trace_data_flow("wdo_ml_snapshot")
        node_ids = {n["id"] for n in graph["nodes"]}
        assert "wdo_ml_snapshot:v1" in node_ids

    def test_trace_snapshot_flow(self):
        graph = ArchitectureTrace().trace_snapshot_flow("ml_pipeline_v1_seed42")
        outputs = {e["output"] for e in graph["edges"]}
        assert any("state_hash" in o or len(o) == 64 for o in outputs)


class TestAuditEventBus:
    def test_emit_and_subscribe_deterministic(self):
        bus_a = AuditEventBus()
        bus_b = AuditEventBus()
        received_a: list[str] = []
        received_b: list[str] = []

        bus_a.subscribe(lambda e: received_a.append(e.event_hash), handler_id="h1")
        bus_b.subscribe(lambda e: received_b.append(e.event_hash), handler_id="h1")

        payload = {"contract_id": "ml_pipeline:v1", "version": "v1"}
        for bus in (bus_a, bus_b):
            bus.emit(AuditEventType.CONTRACT_REGISTERED, payload)
            bus.emit(AuditEventType.CI_GATE_PASSED, {"gate": "contracts"})

        assert bus_a.event_log_hash() == bus_b.event_log_hash()
        assert received_a == received_b

    def test_all_event_types(self):
        bus = AuditEventBus()
        for event_type in AuditEventType:
            event = bus.emit(event_type, {"probe": event_type.value})
            assert event.event_type == event_type
        assert len(bus.list_events()) == len(AuditEventType)


class TestSystemFingerprintLogger:
    def test_system_fingerprint_deterministic(self):
        fp_a = SystemFingerprintLogger().compute_system_fingerprint()
        fp_b = SystemFingerprintLogger().compute_system_fingerprint()
        assert fp_a == fp_b
        assert len(fp_a) == 64

    def test_log_global_state_structure(self):
        state = SystemFingerprintLogger().log_global_state()
        assert "system_fingerprint" in state
        assert set(state["components"]) == {
            "contracts",
            "data",
            "snapshots",
            "evolution",
        }
        assert state["derived_timestamp"].endswith("#system-state")

    def test_component_fingerprints_stable(self):
        logger = SystemFingerprintLogger()
        parts = [
            logger.compute_contracts_fingerprint(),
            logger.compute_data_fingerprint(),
            logger.compute_snapshots_fingerprint(),
            logger.compute_evolution_fingerprint(),
        ]
        assert len(set(parts)) == 4
