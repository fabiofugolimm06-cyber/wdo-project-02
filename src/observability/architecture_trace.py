"""
architecture_trace.py — grafo de dependências contract → data → snapshot.
"""

from __future__ import annotations

from typing import Any

from microstructure.contracts.registry import contract_registry, get_contract


class ArchitectureTrace:
    """
    Traça fluxos arquiteturais como grafo estruturado.

    Formato de aresta: ``node → dependency → output``.
    """

    def trace_contract_flow(self, contract_id: str) -> dict[str, Any]:
        contract = get_contract(contract_id)
        registry_key = contract_registry._resolve_registry_key(contract_id)  # noqa: SLF001

        nodes = [
            {"id": registry_key, "type": "contract", "version": contract.version},
        ]
        edges: list[dict[str, str]] = []

        if contract_id in {"ml_pipeline", "ml_pipeline:v1", "ml_pipeline_contract_v1"}:
            resolved = get_contract("ml_pipeline:v1")
            nodes.append({"id": "ml_pipeline_output", "type": "pipeline_output"})
            edges.append(
                {
                    "node": resolved.contract_id,
                    "dependency": registry_key,
                    "output": "ml_pipeline_output",
                }
            )
            edges.append(
                {
                    "node": "run_ml_pipeline_v1",
                    "dependency": resolved.contract_id,
                    "output": "model_metrics",
                }
            )

        if contract_id in {
            "full_pipeline",
            "full_pipeline:v1",
            "full_pipeline_contract_v1",
        }:
            resolved = get_contract("full_pipeline:v1")
            ml = get_contract("ml_pipeline:v1")
            nodes.extend(
                [
                    {"id": "full_pipeline_output", "type": "pipeline_output"},
                    {"id": ml.contract_id, "type": "contract"},
                ]
            )
            edges.extend(
                [
                    {
                        "node": resolved.contract_id,
                        "dependency": registry_key,
                        "output": "full_pipeline_output",
                    },
                    {
                        "node": "model_metrics",
                        "dependency": ml.contract_id,
                        "output": "backtest_metrics",
                    },
                    {
                        "node": "run_full_pipeline",
                        "dependency": resolved.contract_id,
                        "output": "execution_metrics",
                    },
                ]
            )

        return self._graph(nodes, edges)

    def trace_data_flow(self, dataset_id: str) -> dict[str, Any]:
        from src.ci.data_ci_gate import build_canonical_dataset_registry

        registry, _ = build_canonical_dataset_registry()
        contract = registry.get(dataset_id)

        nodes = [
            {"id": contract.registry_key, "type": "dataset", "symbol": contract.symbol},
            {"id": "ohlcv_features", "type": "feature_engine"},
            {"id": "ml_pipeline_input", "type": "pipeline_input"},
        ]
        edges = [
            {
                "node": contract.registry_key,
                "dependency": contract.source,
                "output": "ohlcv_features",
            },
            {
                "node": "ohlcv_features",
                "dependency": contract.registry_key,
                "output": "ml_pipeline_input",
            },
            {
                "node": "run_ml_pipeline_v1",
                "dependency": "ml_pipeline_input",
                "output": "signals",
            },
        ]
        return self._graph(nodes, edges)

    def trace_snapshot_flow(self, snapshot_id: str) -> dict[str, Any]:
        from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

        registry = bootstrap_baseline_snapshot_registry()
        spec = registry.get(snapshot_id)

        nodes = [
            {"id": snapshot_id, "type": "snapshot_spec", "stage": spec.pipeline_stage},
            {"id": spec.contract_id, "type": "contract"},
            {"id": f"pipeline_{spec.pipeline_stage}", "type": "pipeline"},
        ]
        edges = [
            {
                "node": snapshot_id,
                "dependency": spec.contract_id,
                "output": f"pipeline_{spec.pipeline_stage}",
            },
            {
                "node": f"pipeline_{spec.pipeline_stage}",
                "dependency": snapshot_id,
                "output": "state_hash",
            },
            {
                "node": "snapshot_ci_gate",
                "dependency": snapshot_id,
                "output": spec.state_hash,
            },
        ]
        return self._graph(nodes, edges)

    @staticmethod
    def _graph(
        nodes: list[dict[str, Any]],
        edges: list[dict[str, str]],
    ) -> dict[str, Any]:
        unique_nodes = {n["id"]: n for n in nodes}
        ordered_edges = sorted(
            edges,
            key=lambda e: (e["node"], e["dependency"], e["output"]),
        )
        return {
            "nodes": [unique_nodes[k] for k in sorted(unique_nodes)],
            "edges": ordered_edges,
        }
