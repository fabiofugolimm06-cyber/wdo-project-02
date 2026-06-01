"""
ast_ci_engine.py — seleção inteligente de testes via AST.

Level 2: import graph (file → file)
Level 3: call graph (function → function) — default
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ast_ci_call_graph import (
    CallGraphState,
    CallImpactReport,
    build_call_graph,
    log_call_graph,
    log_call_impact,
    propagate_call_impact,
)
from ci_cache import build_call_graph_cached

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

IGNORE_WALK_DIRS = frozenset(
    {
        "venv",
        ".venv",
        "__pycache__",
        ".git",
        ".pytest_cache",
        "node_modules",
        ".cursor",
        "graficos",
        "data",
        "07_VALIDATION",
        "08_TESTES_15MIN",
    }
)

# Apenas estes .txt são explicitamente irrelevantes para seleção de testes CI.
IRRELEVANT_TXT_FILES = frozenset(
    {
        "requirements-dev.txt",
    }
)

# Extensões não-Python ignoradas na detecção de mudanças (não inclui .txt).
IGNORE_CHANGE_SUFFIXES = frozenset({".md", ".log", ".csv", ".png", ".jpg", ".jpeg"})

# Fallback secundário removido (Level 3): FILE_TO_TESTS não é mais usado na seleção.
# Fallback permitido apenas: function_count == 0 ou nenhum teste mapeado → FULL CI.

FULL_CI_TARGET = "tests"
AST_CI_LEVEL = os.environ.get("AST_CI_LEVEL", "3")


@dataclass
class ChangeReport:
    raw: list[str] = field(default_factory=list)
    filtered: list[str] = field(default_factory=list)
    python_changes: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)


@dataclass
class GraphReport:
    node_count: int = 0
    edge_count: int = 0
    module_index_size: int = 0


@dataclass
class SelectionReport:
    tests: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    fallback_reason: str | None = None
    engine_level: str = "L2"
    call_impact: CallImpactReport | None = None


# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------


def _norm(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _log_section(title: str) -> None:
    print(f"\n=== {title} ===")


def log_change_input(report: ChangeReport) -> None:
    _log_section("PRINT CHANGE INPUT")
    print(f"Raw changes: {len(report.raw)}")
    for path in report.raw[:30]:
        print(f"  raw: {path}")
    if len(report.raw) > 30:
        print(f"  ... (+{len(report.raw) - 30} more)")
    print(f"Filtered (non-ignored): {len(report.filtered)}")
    for path in report.filtered[:30]:
        print(f"  filtered: {path}")
    if len(report.filtered) > 30:
        print(f"  ... (+{len(report.filtered) - 30} more)")
    print(f"Python changes: {len(report.python_changes)}")
    for path in report.python_changes:
        print(f"  python: {path}")
    if report.ignored:
        print(f"Ignored paths: {len(report.ignored)}")
        for path in report.ignored[:20]:
            print(f"  ignored: {path}")


def log_graph(report: GraphReport) -> None:
    _log_section("PRINT GRAPH SIZE")
    print(f"Nodes: {report.node_count}")
    _log_section("PRINT EDGE COUNT")
    print(f"Edges: {report.edge_count}")
    print(f"Module index entries: {report.module_index_size}")


def log_selection(selection: SelectionReport) -> None:
    if selection.call_impact:
        log_call_impact(selection.call_impact)
    _log_section("PRINT SELECTED TESTS")
    print(f"Engine level: {selection.engine_level}")
    print(f"Count: {len(selection.tests)}")
    for test in selection.tests:
        print(f"  test: {test}")
    print(f"Affected files (L2 impact): {len(selection.affected_files)}")
    if selection.fallback_reason:
        _log_section("PRINT FALLBACK REASON")
        print(selection.fallback_reason)


# -----------------------------------------------------------------------------
# 1. DISCOVERY
# -----------------------------------------------------------------------------


def _relative_project_path(path: str | Path, base: Path | None = None) -> str:
    """Normaliza caminho para relativo ao PROJECT_ROOT."""
    root = (base or PROJECT_ROOT).resolve()
    target = Path(path)
    if not target.is_absolute():
        target = (root / target).resolve()
    try:
        return _norm(target.relative_to(root))
    except ValueError:
        return _norm(target)


def get_python_files(root: Path | None = None) -> list[str]:
    """Lista arquivos Python do projeto (paths relativos ao root)."""
    base = (root or PROJECT_ROOT).resolve()
    files: list[str] = []

    for current_root, dirs, filenames in os.walk(base):
        dirs[:] = [d for d in dirs if d not in IGNORE_WALK_DIRS]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            abs_path = Path(current_root) / filename
            rel_path = _relative_project_path(abs_path, base)
            if any(f"/{part}/" in f"/{rel_path}/" for part in IGNORE_WALK_DIRS):
                continue
            files.append(rel_path)

    return sorted(files)


def _is_irrelevant_change(path: str) -> bool:
    normalized = _norm(path)
    if normalized in IRRELEVANT_TXT_FILES:
        return True
    lower = normalized.lower()
    if lower.endswith(tuple(IRRELEVANT_TXT_FILES)):
        return True
    suffix = Path(normalized).suffix.lower()
    if suffix in IGNORE_CHANGE_SUFFIXES:
        return True
    return False


def _git_output(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def get_changed_files() -> ChangeReport:
    """
    Detecta mudanças git (working tree + staged vs HEAD).

    .txt não é filtrado globalmente — apenas entradas em IRRELEVANT_TXT_FILES.
    """
    report = ChangeReport()

    chunks = [
        _git_output(["diff", "--name-only", "HEAD"]),
        _git_output(["diff", "--name-only", "--cached", "HEAD"]),
        _git_output(["ls-files", "--others", "--exclude-standard"]),
    ]
    seen: set[str] = set()
    for chunk in chunks:
        for line in chunk.splitlines():
            line = line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            report.raw.append(_relative_project_path(line))

    report.raw.sort()

    for path in report.raw:
        if _is_irrelevant_change(path):
            report.ignored.append(path)
            continue
        report.filtered.append(path)
        if path.endswith(".py"):
            report.python_changes.append(path)

    _log_section("CHANGE FILTER")
    print(f"Raw changes: {len(report.raw)}")
    print(f"Filtered changes: {len(report.filtered)}")
    print(f"Python changes: {len(report.python_changes)}")

    return report


# -----------------------------------------------------------------------------
# 2. AST PARSER
# -----------------------------------------------------------------------------


def _read_source(path: str) -> str | None:
    file_path = PROJECT_ROOT / path if not Path(path).is_absolute() else Path(path)
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = file_path.read_text(encoding=encoding)
            if text.startswith("\ufeff"):
                text = text.lstrip("\ufeff")
            return text
        except (UnicodeDecodeError, OSError):
            continue
    print(f"WARN parse_imports: unable to read {path}")
    return None


def _module_for_file(file_path: str, root: Path | None = None) -> str | None:
    base = (root or PROJECT_ROOT).resolve()
    path = (PROJECT_ROOT / file_path).resolve()
    try:
        rel = path.relative_to(base)
    except ValueError:
        return None

    if rel.name == "__init__.py":
        parts = rel.parts[:-1]
    else:
        parts = rel.with_suffix("").parts

    if not parts:
        return None
    return ".".join(parts)


def _package_for_file(file_path: str, root: Path | None = None) -> str | None:
    base = (root or PROJECT_ROOT).resolve()
    path = (PROJECT_ROOT / file_path).resolve()
    try:
        rel = path.relative_to(base)
    except ValueError:
        return None

    if rel.name == "__init__.py":
        parts = rel.parts[:-1]
    else:
        parts = rel.parent.parts

    if not parts:
        return None
    return ".".join(parts)


def _resolve_relative(module: str | None, level: int, package: str | None) -> str | None:
    if level <= 0:
        return module
    if not package:
        return None

    parts = package.split(".")
    if level > len(parts):
        return None

    base_parts = parts[:-level] if level <= len(parts) else []
    base = ".".join(base_parts)

    if module:
        return f"{base}.{module}" if base else module
    return base or None


def parse_imports(file_path: str) -> set[str]:
    """Extrai imports absolutos/resolvidos (módulos completos quando possível)."""
    source = _read_source(file_path)
    if source is None:
        return set()

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        print(f"WARN parse_imports: syntax error in {file_path}: {exc}")
        return set()

    package = _package_for_file(file_path)
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_relative(node.module, node.level or 0, package)
            if not resolved:
                continue
            imports.add(resolved)
            # from pkg.mod import a, b → também indexar submódulos explícitos
            for alias in node.names:
                if alias.name == "*":
                    continue
                imports.add(f"{resolved}.{alias.name}")

    return imports


# -----------------------------------------------------------------------------
# 3. MODULE INDEX + GRAPH
# -----------------------------------------------------------------------------


def build_module_index(files: Iterable[str], root: Path | None = None) -> dict[str, str]:
    """Mapeia nome de módulo Python → caminho de arquivo."""
    index: dict[str, str] = {}
    for file_path in files:
        module = _module_for_file(file_path, root)
        if module:
            index[module] = _norm(file_path)
    return index


def resolve_import_to_file(import_name: str, module_index: dict[str, str]) -> str | None:
    """Resolve import para arquivo local via longest-prefix match."""
    parts = import_name.split(".")
    for end in range(len(parts), 0, -1):
        candidate = ".".join(parts[:end])
        if candidate in module_index:
            return module_index[candidate]
    return None


def build_graph(files: Iterable[str], root: Path | None = None) -> tuple[dict[str, set[str]], dict[str, set[str]], GraphReport]:
    """
    Constrói grafo direto e reverso.

    graph[importer] = {imported files}
    reverse[imported] = {importers}
    """
    file_list = sorted({_norm(f) for f in files})
    module_index = build_module_index(file_list, root)

    graph: dict[str, set[str]] = {f: set() for f in file_list}
    reverse: dict[str, set[str]] = {f: set() for f in file_list}

    for file_path in file_list:
        for import_name in parse_imports(file_path):
            target = resolve_import_to_file(import_name, module_index)
            if target is None or target == file_path:
                continue
            if target not in graph:
                continue
            graph[file_path].add(target)
            reverse[target].add(file_path)

    edge_count = sum(len(deps) for deps in graph.values())
    report = GraphReport(
        node_count=len(graph),
        edge_count=edge_count,
        module_index_size=len(module_index),
    )
    return graph, reverse, report


# -----------------------------------------------------------------------------
# 4. IMPACT ANALYSIS
# -----------------------------------------------------------------------------


def get_affected_files(changed_files: Iterable[str], reverse_graph: dict[str, set[str]]) -> set[str]:
    """BFS no grafo reverso — quem importa os arquivos alterados."""
    normalized_changes = {_norm(f) for f in changed_files}
    affected: set[str] = set()
    queue: deque[str] = deque(sorted(normalized_changes))

    while queue:
        current = queue.popleft()
        if current in affected:
            continue
        affected.add(current)
        for dependent in sorted(reverse_graph.get(current, ())):
            if dependent not in affected:
                queue.append(dependent)

    return affected


def _is_test_file(path: str) -> bool:
    normalized = _relative_project_path(path)
    marker = "/tests/"
    if marker in f"/{normalized}/":
        rel = normalized.split("tests/", 1)[-1]
        rel = f"tests/{rel}" if not normalized.startswith("tests/") else normalized
    elif normalized.startswith("tests/"):
        rel = normalized
    else:
        return False
    name = Path(rel).name
    return name.startswith("test_") and name.endswith(".py")


def _select_tests_from_graph(affected_files: Iterable[str]) -> list[str]:
    tests = sorted({_norm(f) for f in affected_files if _is_test_file(f)})
    return tests


def _select_tests_level3(
    change_report: ChangeReport,
    call_state: CallGraphState,
) -> SelectionReport | None:
    """Level 3 — impacto por call graph."""
    if call_state.function_count == 0:
        return None

    impact = propagate_call_impact(change_report.python_changes, call_state)
    if impact.affected_tests:
        selection = SelectionReport(
            tests=impact.affected_tests,
            engine_level="L3",
            call_impact=impact,
        )
        return selection

    return SelectionReport(
        tests=[],
        engine_level="L3",
        call_impact=impact,
    )


def _select_tests_level2(
    change_report: ChangeReport,
    reverse_graph: dict[str, set[str]],
) -> SelectionReport:
    """Level 2 — impacto por import graph (compatibilidade)."""
    selection = SelectionReport(engine_level="L2")
    selection.affected_files = sorted(
        get_affected_files(change_report.python_changes, reverse_graph)
    )
    graph_tests = _select_tests_from_graph(selection.affected_files)
    if graph_tests:
        selection.tests = graph_tests
    return selection


def select_tests(
    change_report: ChangeReport,
    reverse_graph: dict[str, set[str]],
    call_state: CallGraphState | None = None,
) -> SelectionReport:
    """
    Seleciona testes: L3 (call graph) → L2 (import graph) → FULL CI explícito.

    Fallback FULL CI apenas se function_count == 0 ou nenhum teste mapeado após L3+L2.
    """
    selection = SelectionReport()

    if not change_report.python_changes:
        selection.fallback_reason = "no_relevant_python_changes"
        selection.tests = []
        return selection

    if AST_CI_LEVEL != "2" and call_state is not None:
        l3 = _select_tests_level3(change_report, call_state)
        if l3 and l3.tests:
            return l3

    if call_state is not None and call_state.function_count == 0:
        l2 = _select_tests_level2(change_report, reverse_graph)
        if l2.tests:
            l2.fallback_reason = "failsafe_l2_no_function_nodes"
            return l2
        selection.tests = [FULL_CI_TARGET]
        selection.fallback_reason = "full_ci_explicit_no_function_nodes"
        selection.engine_level = "FULL"
        return selection

    l2 = _select_tests_level2(change_report, reverse_graph)
    if l2.tests:
        if call_state is not None:
            l2.call_impact = propagate_call_impact(change_report.python_changes, call_state)
        return l2

    selection.tests = [FULL_CI_TARGET]
    selection.fallback_reason = "full_ci_explicit_no_mapped_tests"
    selection.engine_level = "FULL"
    if call_state is not None:
        selection.call_impact = propagate_call_impact(change_report.python_changes, call_state)
    return selection


# -----------------------------------------------------------------------------
# 5. EXECUÇÃO
# -----------------------------------------------------------------------------


def run_tests(tests: list[str], *, fallback_reason: str | None = None) -> int:
    _log_section("AST CI ENGINE")

    if fallback_reason:
        _log_section("PRINT FALLBACK REASON")
        print(fallback_reason)

    if not tests:
        print("No Python changes detected — skipping pytest.")
        return 0

    cmd = [sys.executable, "-m", "pytest", "-q", "-x", *tests]
    print("Tests selected:", len(tests) if tests != [FULL_CI_TARGET] else "FULL CI")
    print("CMD:", " ".join(cmd))

    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


# -----------------------------------------------------------------------------
# 6. MAIN
# -----------------------------------------------------------------------------


def main() -> int:
    print(f"AST CI STARTED (level={AST_CI_LEVEL})")

    files = get_python_files()
    print(f"Python files found: {len(files)}")

    _graph, reverse_graph, graph_report = build_graph(files)
    log_graph(graph_report)

    change_report = get_changed_files()
    log_change_input(change_report)

    try:
        call_state, cache_report = build_call_graph_cached(
            files,
            changed_files=change_report.python_changes,
        )
        if cache_report.reused:
            print("\n=== CALL GRAPH CACHE ===")
            print("REUSED — no Python structural changes detected")
        elif cache_report.incremental:
            print("\n=== CALL GRAPH CACHE ===")
            print(f"INCREMENTAL — updated {len(cache_report.changed_files)} files")
    except Exception as exc:
        print(f"WARN ast_ci_engine: call graph cache failed ({exc}) — L2 stable fallback")
        call_state = None

    if call_state is not None:
        log_call_graph(call_state)

    selection = select_tests(change_report, reverse_graph, call_state)
    log_selection(selection)

    return run_tests(selection.tests, fallback_reason=selection.fallback_reason)


if __name__ == "__main__":
    raise SystemExit(main())
