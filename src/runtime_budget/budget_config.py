"""
budget_config.py — limites de runtime CI (determinísticos).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetConfig:
    """Limites de budget para pipeline CI."""

    max_total_ci_time: int = 120_000  # ms sintético total
    max_gate_time: int = 15_000  # ms sintético por gate
    max_memory_usage: int = 4096  # MB — referência de cap
    max_cpu_threads: int = 4

    def to_dict(self) -> dict[str, int]:
        return {
            "max_total_ci_time": self.max_total_ci_time,
            "max_gate_time": self.max_gate_time,
            "max_memory_usage": self.max_memory_usage,
            "max_cpu_threads": self.max_cpu_threads,
        }


DEFAULT_BUDGET = BudgetConfig()
