"""
ast_ci_engine.py — seleção inteligente de testes via grafo de imports AST.

Pipeline: change detection → dependency graph → impact BFS → test selection.
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

# Fallback final opcional — só quando há mudança Python mas grafo não alcança testes.
FILE_TO_TESTS: dict[str, list[str]] = {
    "pipeline": [
        "tests/test_pipeline_regression.py",
        "tests/test_ci_stress_reliability.py",
    ],
    "model": [
        "tests/test_pipeline_regression.py",
    ],
    "contract": [
        "tests/test_contract_enforcement.py",
    ],
    "ci": [
        "tests/test_ci_stress_reliability.py",
    ],
}

CORE_TESTS = [
    "tests/test_pipeline_regression.py",
    "tests/test_ci_stress_reliability.py",
    "tests/test_contract_enforcement.py",
]

MAX_SELECTED_TESTS = 200


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
    _log_section("PRINT SELECTED TESTS")
    print(f"Count: {len(selection.tests)}")
    for test in selection.tests:
        print(f"  test: {test}")
    print(f"Affected files (impact): {len(selection.affected_files)}")
    if selection.fallback_reason:
        _log_section("PRINT FALLBACK REASON")
        print(selection.fallback_reason)


# -----------------------------------------------------------------------------
# 1. DISCOVERY
# -----------------------------------------------------------------------------


def get_python_files(root: Path | None = None) -> list[str]:
    """Lista arquivos Python do projeto (scan amplo, sem excluir src/tests/scripts)."""
    base = root or PROJECT_ROOT
    files: list[str] = []

    for current_root, dirs, filenames in os.walk(base):
        dirs[:] = [d for d in dirs if d not in IGNORE_WALK_DIRS]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = _norm(Path(current_root) / filename)
            if any(f"/{part}/" in f"/{path}/" for part in IGNORE_WALK_DIRS):
                continue
            files.append(path)

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
            report.raw.append(_norm(line))

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
    queue: deque[str] = deque()

    for path in normalized_changes:
        if path in reverse_graph or path.endswith(".py"):
            queue.append(path)

    while queue:
        current = queue.popleft()
        if current in affected:
            continue
        affected.add(current)
        for dependent in reverse_graph.get(current, ()):
            queue.append(dependent)

    return affected


def _is_test_file(path: str) -> bool:
    normalized = _norm(path)
    name = Path(normalized).name
    return normalized.startswith("tests/") and name.startswith("test_") and name.endswith(".py")


def _select_tests_from_graph(affected_files: Iterable[str]) -> list[str]:
    tests = sorted({_norm(f) for f in affected_files if _is_test_file(f)})
    return tests


def _select_tests_from_fallback(changed_python: Iterable[str]) -> list[str]:
    selected: set[str] = set()
    for path in changed_python:
        blob = _norm(path).lower()
        for key, related in FILE_TO_TESTS.items():
            if key in blob:
                selected.update(related)
    return sorted(selected)


def select_tests(
    change_report: ChangeReport,
    reverse_graph: dict[str, set[str]],
) -> SelectionReport:
    """Seleciona testes via grafo; fallback só com mudança Python sem testes alcançados."""
    selection = SelectionReport()

    if not change_report.python_changes:
        selection.fallback_reason = "no_relevant_python_changes"
        selection.tests = []
        return selection

    selection.affected_files = sorted(
        get_affected_files(change_report.python_changes, reverse_graph)
    )
    graph_tests = _select_tests_from_graph(selection.affected_files)

    if graph_tests:
        selection.tests = graph_tests
        return selection

    fallback_tests = _select_tests_from_fallback(change_report.python_changes)
    if fallback_tests:
        selection.tests = fallback_tests
        selection.fallback_reason = "graph_miss_using_file_to_tests"
        return selection

    selection.tests = CORE_TESTS.copy()
    selection.fallback_reason = "graph_miss_using_core_tests"
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

    if len(tests) > MAX_SELECTED_TESTS:
        print(
            f"WARN: {len(tests)} tests selected (> {MAX_SELECTED_TESTS}); "
            "truncating to limit (not full CI)."
        )
        tests = tests[:MAX_SELECTED_TESTS]

    cmd = [sys.executable, "-m", "pytest", "-q", "-x", *tests]
    print("Tests selected:", len(tests))
    print("CMD:", " ".join(cmd))

    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


# -----------------------------------------------------------------------------
# 6. MAIN
# -----------------------------------------------------------------------------


def main() -> int:
    print("AST CI STARTED")

    files = get_python_files()
    print(f"Python files found: {len(files)}")

    _graph, reverse_graph, graph_report = build_graph(files)
    log_graph(graph_report)

    change_report = get_changed_files()
    log_change_input(change_report)

    selection = select_tests(change_report, reverse_graph)
    log_selection(selection)

    return run_tests(selection.tests, fallback_reason=selection.fallback_reason)


if __name__ == "__main__":
    raise SystemExit(main())
