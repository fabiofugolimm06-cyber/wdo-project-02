"""
execution_caps.py — caps de paralelismo e picos de recurso.
"""

from __future__ import annotations

import os
from typing import Any

from src.runtime_budget.budget_config import BudgetConfig, DEFAULT_BUDGET


class ExecutionCaps:
    """Limita execução paralela e picos de recurso."""

    _MAX_PARALLEL_GROUPS: int = 2

    def __init__(self, budget: BudgetConfig | None = None) -> None:
        self.budget = budget or DEFAULT_BUDGET

    def cap_parallel_execution(self, parallel_groups: list[list[str]]) -> dict[str, Any]:
        capped: list[list[str]] = []
        for group in parallel_groups[: self._MAX_PARALLEL_GROUPS]:
            capped.append(sorted(group))
        return {
            "original_group_count": len(parallel_groups),
            "capped_group_count": len(capped),
            "capped_groups": capped,
            "max_parallel_groups": self._MAX_PARALLEL_GROUPS,
        }

    def limit_resource_spikes(self) -> dict[str, Any]:
        failures: list[str] = []
        threads = int(os.environ.get("OMP_NUM_THREADS", "1") or "1")
        if threads > self.budget.max_cpu_threads:
            failures.append(
                f"resource: OMP_NUM_THREADS={threads} > max={self.budget.max_cpu_threads}."
            )

        capped_threads = min(threads, self.budget.max_cpu_threads)
        return {
            "status": "PASS" if not failures else "FAIL",
            "failures": sorted(failures),
            "effective_threads": capped_threads,
            "max_cpu_threads": self.budget.max_cpu_threads,
        }
