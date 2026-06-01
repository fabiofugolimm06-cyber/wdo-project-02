"""
ci_cache.py — Production caching layer for AST CI (call graph + AST parse).
"""

from __future__ import annotations

import hashlib
import json
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ast_ci_call_graph import (
    CallGraphState,
    FunctionNode,
    _forward_closure_from_tests,
    _is_test_file,
    _norm,
    _parse_file,
    build_module_index,
)

PROJECT_ROOT = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_ROOT / "ci_cache"
AST_CACHE_PATH = CACHE_DIR / "ast_cache.pkl"
CALL_GRAPH_CACHE_PATH = CACHE_DIR / "call_graph_cache.pkl"
PERF_METRICS_PATH = PROJECT_ROOT / "ci_perf_metrics.json"
CACHE_VERSION = 1


@dataclass
class CacheBuildReport:
    reused: bool = False
    incremental: bool = False
    changed_files: list[str] = field(default_factory=list)
    ast_cache_hits: int = 0
    ast_cache_misses: int = 0
    parse_time_ms: int = 0
    graph_build_time_ms: int = 0


@dataclass
class PerfMetrics:
    ast_parse_time_ms: int = 0
    graph_build_time_ms: int = 0
    test_selection_time_ms: int = 0
    test_execution_time_ms: int = 0
    total_ci_runtime_ms: int = 0
    cache_reused: bool = False
    ast_cache_hits: int = 0
    ast_cache_misses: int = 0
    incremental_update: bool = False
    pruned_edges: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ast_parse_time_ms": self.ast_parse_time_ms,
            "graph_build_time_ms": self.graph_build_time_ms,
            "test_selection_time_ms": self.test_selection_time_ms,
            "test_execution_time_ms": self.test_execution_time_ms,
            "total_ci_runtime_ms": self.total_ci_runtime_ms,
            "cache_reused": self.cache_reused,
            "ast_cache_hits": self.ast_cache_hits,
            "ast_cache_misses": self.ast_cache_misses,
            "incremental_update": self.incremental_update,
            "pruned_edges": self.pruned_edges,
        }


_ast_cache_stats = {"hits": 0, "misses": 0}


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def file_sha256(file_path: str) -> str | None:
    path = PROJECT_ROOT / file_path if not Path(file_path).is_absolute() else Path(file_path)
    if not path.exists():
        return None
    digest = hashlib.sha256()
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            data = path.read_bytes()
            digest.update(data)
            return digest.hexdigest()
        except OSError:
            continue
    return None


def compute_file_hashes(files: Iterable[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for file_path in sorted({_norm(f) for f in files}):
        digest = file_sha256(file_path)
        if digest:
            hashes[file_path] = digest
    return hashes


def load_ast_cache() -> dict[str, dict[str, Any]]:
    _ensure_cache_dir()
    if not AST_CACHE_PATH.exists():
        return {}
    try:
        with AST_CACHE_PATH.open("rb") as handle:
            payload = pickle.load(handle)
        if isinstance(payload, dict):
            return payload
    except (OSError, pickle.PickleError, EOFError, UnicodeDecodeError, ValueError):
        print("WARN ci_cache: ast cache load failed — rebuilding")
        try:
            AST_CACHE_PATH.unlink(missing_ok=True)
        except OSError:
            pass
    return {}


def save_ast_cache(cache: dict[str, dict[str, Any]]) -> None:
    _ensure_cache_dir()
    with AST_CACHE_PATH.open("wb") as handle:
        pickle.dump(cache, handle, protocol=pickle.HIGHEST_PROTOCOL)


def get_cached_ast(file_path: str, source: str) -> Any:
    """Return cached AST tree or parse and store."""
    import ast

    normalized = _norm(file_path)
    digest = hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest()
    cache = load_ast_cache()
    entry = cache.get(normalized)
    if entry and entry.get("hash") == digest and entry.get("tree") is not None:
        _ast_cache_stats["hits"] += 1
        return entry["tree"]

    tree = ast.parse(source, filename=normalized)
    cache[normalized] = {"hash": digest, "tree": tree}
    save_ast_cache(cache)
    _ast_cache_stats["misses"] += 1
    return tree


def reset_ast_cache_stats() -> None:
    _ast_cache_stats["hits"] = 0
    _ast_cache_stats["misses"] = 0


def get_ast_cache_stats() -> tuple[int, int]:
    return _ast_cache_stats["hits"], _ast_cache_stats["misses"]


def load_cached_call_graph() -> tuple[CallGraphState | None, dict[str, str]]:
    _ensure_cache_dir()
    if not CALL_GRAPH_CACHE_PATH.exists():
        return None, {}
    try:
        with CALL_GRAPH_CACHE_PATH.open("rb") as handle:
            payload = pickle.load(handle)
        if not isinstance(payload, dict):
            return None, {}
        if payload.get("version") != CACHE_VERSION:
            return None, {}
        state = payload.get("state")
        hashes = payload.get("file_hashes", {})
        if isinstance(state, CallGraphState) and isinstance(hashes, dict):
            return state, {str(k): str(v) for k, v in hashes.items()}
    except (OSError, pickle.PickleError, EOFError, UnicodeDecodeError, ValueError):
        print("WARN ci_cache: call graph cache load failed — rebuilding")
        try:
            CALL_GRAPH_CACHE_PATH.unlink(missing_ok=True)
        except OSError:
            pass
    return None, {}


def save_call_graph_cache(state: CallGraphState, file_hashes: dict[str, str]) -> None:
    _ensure_cache_dir()
    payload = {
        "version": CACHE_VERSION,
        "state": state,
        "file_hashes": file_hashes,
    }
    with CALL_GRAPH_CACHE_PATH.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)


def _remove_file_from_state(state: CallGraphState, file_path: str) -> None:
    normalized = _norm(file_path)
    keys = list(state.functions_by_file.get(normalized, []))
    removed_keys = set(keys)
    for key in keys:
        state.function_index.pop(key, None)
        state.call_graph.pop(key, None)
        for callee in list(state.reverse_call_graph.keys()):
            state.reverse_call_graph[callee] = {
                caller for caller in state.reverse_call_graph[callee] if caller != key
            }
        state.reverse_call_graph.pop(key, None)

    for caller, callees in list(state.call_graph.items()):
        stale = callees & removed_keys
        for callee in stale:
            callees.discard(callee)
            state.reverse_call_graph[callee].discard(caller)

    state.functions_by_file.pop(normalized, None)
    state.test_exercised_functions.pop(normalized, None)
    for fn_key in list(state.function_to_tests.keys()):
        if fn_key in removed_keys:
            state.function_to_tests.pop(fn_key, None)


def _rebuild_test_mappings(state: CallGraphState, file_list: list[str]) -> None:
    state.test_exercised_functions.clear()
    state.function_to_tests.clear()
    for file_path in file_list:
        if not _is_test_file(file_path):
            continue
        exercised = _forward_closure_from_tests(file_path, state)
        state.test_exercised_functions[file_path] = exercised
        for fn_key in sorted(exercised):
            state.function_to_tests.setdefault(fn_key, set()).add(file_path)


def _full_build_call_graph(file_list: list[str]) -> CallGraphState:
    module_index = build_module_index(file_list)
    state = CallGraphState()

    for file_path in file_list:
        defined, _ = _parse_file(file_path, module_index, state.function_index)
        for fn in defined:
            state.function_index[fn.key] = fn
            state.functions_by_file.setdefault(fn.file_path, []).append(fn.key)

    for file_path in file_list:
        _, edges = _parse_file(file_path, module_index, state.function_index)
        for caller, callee in edges:
            state.call_graph[caller].add(callee)
            state.reverse_call_graph[callee].add(caller)

    state.function_count = len(state.function_index)
    state.call_edge_count = sum(len(v) for v in state.call_graph.values())
    _rebuild_test_mappings(state, file_list)
    return state


def _incremental_build_call_graph(
    state: CallGraphState,
    file_list: list[str],
    changed_files: list[str],
) -> CallGraphState:
    module_index = build_module_index(file_list)
    for file_path in changed_files:
        _remove_file_from_state(state, file_path)

    for file_path in changed_files:
        defined, _ = _parse_file(file_path, module_index, state.function_index)
        for fn in defined:
            state.function_index[fn.key] = fn
            state.functions_by_file.setdefault(fn.file_path, []).append(fn.key)

    for file_path in file_list:
        _, edges = _parse_file(file_path, module_index, state.function_index)
        for caller, callee in edges:
            if caller in state.function_index and callee in state.function_index:
                state.call_graph[caller].add(callee)
                state.reverse_call_graph[callee].add(caller)

    state.function_count = len(state.function_index)
    state.call_edge_count = sum(len(v) for v in state.call_graph.values())
    _rebuild_test_mappings(state, file_list)
    return state


def prune_call_graph(state: CallGraphState, history: list[dict[str, Any]], *, min_runs: int = 20) -> int:
    """Remove edges not referenced in recent execution impact sets."""
    if len(history) < min_runs:
        return 0

    used_functions: set[str] = set()
    for row in history[-min_runs:]:
        for fn in row.get("affected_functions", []):
            used_functions.add(fn)

    if not used_functions:
        return 0

    pruned = 0
    for caller in sorted(state.call_graph.keys()):
        callees = state.call_graph[caller]
        to_remove = {
            callee
            for callee in callees
            if caller not in used_functions and callee not in used_functions
        }
        for callee in to_remove:
            callees.discard(callee)
            state.reverse_call_graph[callee].discard(caller)
            pruned += 1

    state.call_edge_count = sum(len(v) for v in state.call_graph.values())
    return pruned


def build_call_graph_cached(
    files: Iterable[str],
    *,
    changed_files: Iterable[str] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> tuple[CallGraphState, CacheBuildReport]:
    """Build or reuse call graph with AST + graph caching."""
    reset_ast_cache_stats()
    started = time.perf_counter()
    report = CacheBuildReport()
    file_list = sorted({_norm(f) for f in files})
    current_hashes = compute_file_hashes(file_list)

    cached_state, cached_hashes = load_cached_call_graph()
    changed = sorted(path for path, digest in current_hashes.items() if cached_hashes.get(path) != digest)
    report.changed_files = changed

    if cached_state is not None and not changed:
        report.reused = True
        hits, misses = get_ast_cache_stats()
        report.ast_cache_hits = hits
        report.ast_cache_misses = misses
        report.graph_build_time_ms = int((time.perf_counter() - started) * 1000)
        if history:
            prune_call_graph(cached_state, history)
        return cached_state, report

    if cached_state is not None and changed and len(changed) <= max(20, len(file_list) // 5):
        state = _incremental_build_call_graph(cached_state, file_list, changed)
        report.incremental = True
    else:
        state = _full_build_call_graph(file_list)

    if history:
        prune_call_graph(state, history)

    save_call_graph_cache(state, current_hashes)
    hits, misses = get_ast_cache_stats()
    report.ast_cache_hits = hits
    report.ast_cache_misses = misses
    report.graph_build_time_ms = int((time.perf_counter() - started) * 1000)
    return state, report


def save_perf_metrics(metrics: PerfMetrics) -> None:
    payload = metrics.to_dict()
    existing: list[dict[str, Any]] = []
    if PERF_METRICS_PATH.exists():
        try:
            raw = json.loads(PERF_METRICS_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing = raw
            elif isinstance(raw, dict):
                existing = raw.get("runs", [])
        except (json.JSONDecodeError, OSError):
            existing = []
    existing.append(payload)
    PERF_METRICS_PATH.write_text(
        json.dumps({"runs": existing[-100:]}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
