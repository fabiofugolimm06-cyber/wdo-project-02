"""Redundancy Final Check — overlap e equivalência comportamental."""

from src.redundancy_final.final_consolidation_gate import (
    assert_deterministic_output,
    assert_zero_behavioral_drift,
    run_final_consolidation_gate,
    run_full_system_equivalence_check,
    validate_pipeline_reduction_integrity,
)
from src.redundancy_final.system_overlap_analyzer import (
    CONSOLIDATED_COVERAGE,
    SystemOverlapAnalyzer,
)
from src.redundancy_final.validation_equivalence_engine import (
    ValidationEquivalenceEngine,
    compute_behavioral_fingerprint,
)

__all__ = [
    "CONSOLIDATED_COVERAGE",
    "SystemOverlapAnalyzer",
    "ValidationEquivalenceEngine",
    "assert_deterministic_output",
    "assert_zero_behavioral_drift",
    "compute_behavioral_fingerprint",
    "run_final_consolidation_gate",
    "run_full_system_equivalence_check",
    "validate_pipeline_reduction_integrity",
]
