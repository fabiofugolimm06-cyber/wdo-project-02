"""
trace_compressor.py — compressão determinística de traces de execução.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class TraceCompressor:
    """Remove eventos estruturalmente redundantes preservando semântica."""

    _REDUNDANT_KEYS = frozenset({"derived_timestamp", "sequence"})

    def compress_execution_trace(self, trace: dict[str, Any]) -> dict[str, Any]:
        nodes = trace.get("nodes", [])
        edges = trace.get("edges", [])

        unique_nodes: dict[str, dict[str, Any]] = {}
        for node in nodes:
            node_id = node.get("id", "")
            if node_id not in unique_nodes:
                unique_nodes[node_id] = node

        unique_edges: list[dict[str, str]] = []
        seen_edges: set[tuple[str, str, str]] = set()
        for edge in edges:
            key = (
                edge.get("node", ""),
                edge.get("dependency", ""),
                edge.get("output", ""),
            )
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(edge)

        compressed = {
            "nodes": [unique_nodes[k] for k in sorted(unique_nodes)],
            "edges": sorted(
                unique_edges,
                key=lambda e: (e.get("node", ""), e.get("dependency", ""), e.get("output", "")),
            ),
        }
        return {
            "trace": compressed,
            "original_nodes": len(nodes),
            "compressed_nodes": len(compressed["nodes"]),
            "original_edges": len(edges),
            "compressed_edges": len(compressed["edges"]),
            "trace_hash": self._hash_trace(compressed),
        }

    def remove_redundant_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen_signatures: set[str] = set()
        for event in events:
            semantic = {
                k: v for k, v in sorted(event.items()) if k not in self._REDUNDANT_KEYS
            }
            sig = self._hash_payload(semantic)
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)
            deduped.append(semantic)
        return deduped

    @staticmethod
    def _hash_payload(payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _hash_trace(self, trace: dict[str, Any]) -> str:
        return self._hash_payload(trace)
