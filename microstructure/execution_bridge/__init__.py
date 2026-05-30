"""
microstructure.execution_bridge — Execution Abstraction Layer (Stage 21).
"""

from microstructure.execution_bridge.bridge import ExecutionBridge
from microstructure.execution_bridge.exporters import (
    export_bridge_json,
    export_to_bridge_format,
    export_to_ntsl,
    send_to_execution_layer,
    signal_to_action,
)

__all__ = [
    "ExecutionBridge",
    "export_to_ntsl",
    "export_to_bridge_format",
    "export_bridge_json",
    "send_to_execution_layer",
    "signal_to_action",
]
