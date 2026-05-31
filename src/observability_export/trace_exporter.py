"""
trace_exporter.py — exportação de traces e grafo de dependências.
"""

from __future__ import annotations

from typing import Any

from src.observability import ArchitectureTrace
from src.observability.trace_compressor import TraceCompressor


class TraceExporter:
    """Exporta traces e dependências para observabilidade externa."""

    def export_execution_trace(self) -> dict[str, Any]:
        trace = ArchitectureTrace().trace_contract_flow("ml_pipeline:v1")
        compressed = TraceCompressor().compress_execution_trace(trace)
        return {
            "trace_hash": compressed["trace_hash"],
            "nodes": compressed["compressed_nodes"],
            "edges": compressed["compressed_edges"],
            "trace": compressed["trace"],
        }

    def export_dependency_graph(self) -> dict[str, Any]:
        from src.simplification.dependency_map import DependencyMap

        graph = DependencyMap().build_full_dependency_graph()
        coupling = DependencyMap().compute_layer_coupling()
        return {
            "nodes": graph["nodes"],
            "edges": graph["edges"],
            "avg_coupling": coupling["avg_coupling"],
            "total_edges": coupling["total_edges"],
        }
