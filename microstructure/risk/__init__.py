"""
microstructure.risk — Risk Engine (Stage 17) + Risk Guardian (Stage 22).
"""

from microstructure.risk.risk_engine import (
    calculate_position_size,
    check_daily_loss_limit,
    check_max_drawdown,
    risk_filter,
)
from microstructure.risk.risk_guardian_v1 import RiskGuardianV1

__all__ = [
    "RiskGuardianV1",
    "RiskGuardianFilterAdapter",
    "GuardedExecutionBridge",
    "GuardedPaperTradingEngine",
    "guarded_run_decision_pipeline",
    "apply_guardian_to_decision",
    "state_from_paper",
    "state_from_bridge_snapshot",
    "calculate_position_size",
    "check_daily_loss_limit",
    "check_max_drawdown",
    "risk_filter",
]

_LAZY_EXPORTS = {
    "RiskGuardianFilterAdapter": (
        "microstructure.risk.guardian_integration_v1",
        "RiskGuardianFilterAdapter",
    ),
    "GuardedExecutionBridge": (
        "microstructure.risk.guardian_integration_v1",
        "GuardedExecutionBridge",
    ),
    "GuardedPaperTradingEngine": (
        "microstructure.risk.guardian_integration_v1",
        "GuardedPaperTradingEngine",
    ),
    "guarded_run_decision_pipeline": (
        "microstructure.risk.guardian_integration_v1",
        "guarded_run_decision_pipeline",
    ),
    "apply_guardian_to_decision": (
        "microstructure.risk.guardian_integration_v1",
        "apply_guardian_to_decision",
    ),
    "state_from_paper": (
        "microstructure.risk.guardian_integration_v1",
        "state_from_paper",
    ),
    "state_from_bridge_snapshot": (
        "microstructure.risk.guardian_integration_v1",
        "state_from_bridge_snapshot",
    ),
}


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        module_path, attr = _LAZY_EXPORTS[name]
        import importlib

        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
