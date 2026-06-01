"""
ast_ci_call_graph.py — Level 3: call graph real (function → function).
"""

from __future__ import annotations

import ast
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent


def _norm(path: str | Path) -> str:
    return str(path).replace("\\", "/")


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
    print(f"WARN call_graph: unable to read {path}")
    return None


def _module_for_file(file_path: str) -> str | None:
    path = (PROJECT_ROOT / file_path).resolve()
    try:
        rel = path.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return None
    if rel.name == "__init__.py":
        parts = rel.parts[:-1]
    else:
        parts = rel.with_suffix("").parts
    return ".".join(parts) if parts else None


def _package_for_file(file_path: str) -> str | None:
    path = (PROJECT_ROOT / file_path).resolve()
    try:
        rel = path.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return None
    parts = rel.parts[:-1] if rel.name == "__init__.py" else rel.parent.parts
    return ".".join(parts) if parts else None


def _resolve_relative(module: str | None, level: int, package: str | None) -> str | None:
    if level <= 0:
        return module
    if not package:
        return None
    parts = package.split(".")
    if level > len(parts):
        return None
    base = ".".join(parts[:-level])
    if module:
        return f"{base}.{module}" if base else module
    return base or None


def build_module_index(files: Iterable[str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for file_path in files:
        module = _module_for_file(file_path)
        if module:
            index[module] = _norm(file_path)
    return index


def resolve_import_to_file(import_name: str, module_index: dict[str, str]) -> str | None:
    parts = import_name.split(".")
    for end in range(len(parts), 0, -1):
        candidate = ".".join(parts[:end])
        if candidate in module_index:
            return module_index[candidate]
    return None


@dataclass(frozen=True)
class FunctionNode:
    key: str
    file_path: str
    name: str
    qualname: str
    lineno: int


@dataclass
class CallGraphState:
    function_index: dict[str, FunctionNode] = field(default_factory=dict)
    functions_by_file: dict[str, list[str]] = field(default_factory=dict)
    call_graph: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    reverse_call_graph: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    test_exercised_functions: dict[str, set[str]] = field(default_factory=dict)
    function_to_tests: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    function_count: int = 0
    call_edge_count: int = 0


@dataclass
class CallImpactReport:
    affected_functions: set[str] = field(default_factory=set)
    affected_tests: list[str] = field(default_factory=list)
    propagation_depth: int = 0
    engine_level: str = "L3"


def _function_key(file_path: str, qualname: str) -> str:
    return f"{_norm(file_path)}::{qualname}"


def _is_test_file(path: str) -> bool:
    normalized = _norm(path)
    marker = "/tests/"
    if marker in normalized:
        rel = normalized.split(marker, 1)[1]
        rel = f"tests/{rel}"
    elif normalized.startswith("tests/"):
        rel = normalized
    else:
        return False
    name = Path(rel).name
    return name.startswith("test_") and name.endswith(".py")


MODULE_PREFIX = "@mod:"


def _module_ref(file_path: str) -> str:
    return f"{MODULE_PREFIX}{_norm(file_path)}"


def _is_module_ref(value: str) -> bool:
    return value.startswith(MODULE_PREFIX)


def _module_ref_path(value: str) -> str:
    return value[len(MODULE_PREFIX) :]


def _extract_call_target(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts: list[str] = []
        current: ast.expr = func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
    return None


def _build_import_symbol_map(
    tree: ast.AST,
    file_path: str,
    module_index: dict[str, str],
    function_index: dict[str, FunctionNode],
) -> dict[str, str]:
    package = _package_for_file(file_path)
    symbol_map: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[-1]
                target_file = resolve_import_to_file(alias.name, module_index)
                if not target_file:
                    continue
                symbol_map[local] = _module_ref(target_file)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_relative(node.module, node.level or 0, package)
            if not resolved:
                continue
            target_file = resolve_import_to_file(resolved, module_index)
            if not target_file:
                continue
            normalized_target = _norm(target_file)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                matched = False
                for fk, fn in function_index.items():
                    if fn.file_path == normalized_target and (
                        fn.qualname == alias.name or fn.name == alias.name
                    ):
                        symbol_map[local] = fk
                        matched = True
                        break
                if not matched:
                    submodule = resolve_import_to_file(f"{resolved}.{alias.name}", module_index)
                    if submodule:
                        symbol_map[local] = _module_ref(submodule)
                    else:
                        symbol_map[local] = _module_ref(target_file)
    return symbol_map


class _FunctionCallVisitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        file_path: str,
        import_map: dict[str, str],
    ) -> None:
        self.file_path = _norm(file_path)
        self.import_map = import_map
        self.local_functions: dict[str, str] = {}
        self.class_stack: list[str] = []
        self.current_function: str | None = None
        self.defined: list[FunctionNode] = []
        self.edges: list[tuple[str, str]] = []

    def _qualname(self, name: str) -> str:
        if self.class_stack:
            return ".".join(self.class_stack + [name])
        return name

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qualname = self._qualname(node.name)
        key = _function_key(self.file_path, qualname)
        fn = FunctionNode(
            key=key,
            file_path=self.file_path,
            name=node.name,
            qualname=qualname,
            lineno=node.lineno,
        )
        self.defined.append(fn)
        self.local_functions[node.name] = key
        self.local_functions[qualname] = key
        previous = self.current_function
        self.current_function = key
        for child in node.body:
            self.visit(child)
        self.current_function = previous

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        qualname = self._qualname(node.name)
        key = _function_key(self.file_path, qualname)
        fn = FunctionNode(
            key=key,
            file_path=self.file_path,
            name=node.name,
            qualname=qualname,
            lineno=node.lineno,
        )
        self.defined.append(fn)
        self.local_functions[node.name] = key
        self.local_functions[qualname] = key
        previous = self.current_function
        self.current_function = key
        for child in node.body:
            self.visit(child)
        self.current_function = previous

    def _lookup_in_file(
        self,
        file_path: str,
        attr_path: str,
        function_index: dict[str, FunctionNode],
    ) -> str | None:
        candidate = _function_key(file_path, attr_path)
        if candidate in function_index:
            return candidate
        attr_name = attr_path.split(".")[-1]
        for fk, fn in function_index.items():
            if fn.file_path == _norm(file_path) and (
                fn.qualname == attr_path or fn.name == attr_name
            ):
                return fk
        return None

    def _resolve_callee(self, target: str, function_index: dict[str, FunctionNode]) -> str | None:
        if target in self.local_functions:
            return self.local_functions[target]

        if target.startswith("self.") and self.class_stack:
            method = target.split(".", 1)[1]
            qualname = ".".join(self.class_stack + [method.split(".")[0]])
            if qualname in self.local_functions:
                return self.local_functions[qualname]

        if target in self.import_map:
            imported = self.import_map[target]
            if _is_module_ref(imported):
                return None
            return imported

        base = target.split(".")[0]
        if base in self.import_map:
            imported = self.import_map[base]
            if "." not in target:
                if _is_module_ref(imported):
                    return None
                return imported
            imp_file = (
                _module_ref_path(imported)
                if _is_module_ref(imported)
                else imported.split("::")[0]
            )
            attr = target.split(".", 1)[1]
            resolved = self._lookup_in_file(imp_file, attr, function_index)
            if resolved:
                return resolved

        if "." in target:
            candidate = _function_key(self.file_path, target)
            if candidate in function_index:
                return candidate
            tail = self.local_functions.get(target.split(".")[-1])
            if tail:
                return tail

        return None

    def visit_Call(self, node: ast.Call) -> None:
        if self.current_function:
            target = _extract_call_target(node)
            if target:
                callee = self._resolve_callee(target, getattr(self, "_function_index", {}))
                if callee and callee != self.current_function:
                    self.edges.append((self.current_function, callee))
        self.generic_visit(node)


def _parse_file(
    file_path: str,
    module_index: dict[str, str],
    function_index: dict[str, FunctionNode],
) -> tuple[list[FunctionNode], list[tuple[str, str]]]:
    source = _read_source(file_path)
    if source is None:
        return [], []

    try:
        from ci_cache import get_cached_ast

        tree = get_cached_ast(file_path, source)
    except SyntaxError as exc:
        print(f"WARN call_graph: syntax error in {file_path}: {exc}")
        return [], []

    import_map = _build_import_symbol_map(tree, file_path, module_index, function_index)
    visitor = _FunctionCallVisitor(file_path=file_path, import_map=import_map)
    visitor._function_index = function_index  # type: ignore[attr-defined]
    visitor.visit(tree)

    edges: list[tuple[str, str]] = []
    for caller, callee in visitor.edges:
        if caller in function_index and callee in function_index:
            edges.append((caller, callee))

    return visitor.defined, edges


def build_call_graph(files: Iterable[str]) -> CallGraphState:
    file_list = sorted({_norm(f) for f in files})
    module_index = build_module_index(file_list)
    state = CallGraphState()

    for file_path in file_list:
        defined, _ = _parse_file(file_path, module_index, state.function_index)
        for fn in defined:
            state.function_index[fn.key] = fn
            state.functions_by_file.setdefault(fn.file_path, []).append(fn.key)

    state.function_count = len(state.function_index)

    for file_path in file_list:
        _, edges = _parse_file(file_path, module_index, state.function_index)
        for caller, callee in edges:
            state.call_graph[caller].add(callee)
            state.reverse_call_graph[callee].add(caller)

    state.call_edge_count = sum(len(v) for v in state.call_graph.values())

    for file_path in file_list:
        if not _is_test_file(file_path):
            continue
        exercised = _forward_closure_from_tests(file_path, state)
        state.test_exercised_functions[file_path] = exercised
        for fn_key in exercised:
            state.function_to_tests[fn_key].add(file_path)

    return state


def _forward_closure_from_tests(test_file: str, state: CallGraphState) -> set[str]:
    exercised: set[str] = set()
    starters = sorted(
        fk
        for fk in state.functions_by_file.get(_norm(test_file), [])
        if state.function_index[fk].name.startswith("test_")
    )
    queue: deque[str] = deque(starters)
    while queue:
        current = queue.popleft()
        if current in exercised:
            continue
        exercised.add(current)
        for callee in sorted(state.call_graph.get(current, ())):
            queue.append(callee)
    return exercised


def propagate_call_impact(
    changed_python_files: Iterable[str],
    state: CallGraphState,
) -> CallImpactReport:
    report = CallImpactReport()
    seed_functions: set[str] = set()
    for path in sorted({_norm(f) for f in changed_python_files}):
        seed_functions.update(state.functions_by_file.get(path, ()))

    if not seed_functions:
        return report

    affected = set(seed_functions)
    queue: deque[tuple[str, int]] = deque(sorted((fn, 0) for fn in seed_functions))
    max_depth = 0

    while queue:
        fn_key, depth = queue.popleft()
        max_depth = max(max_depth, depth)
        for caller in sorted(state.reverse_call_graph.get(fn_key, ())):
            if caller not in affected:
                affected.add(caller)
                queue.append((caller, depth + 1))

    report.affected_functions = affected
    report.propagation_depth = max_depth

    tests: set[str] = set()
    for fn_key in affected:
        tests.update(state.function_to_tests.get(fn_key, ()))
    report.affected_tests = sorted(tests)
    return report


def log_call_graph(state: CallGraphState) -> None:
    print("\n=== FUNCTION COUNT ===")
    print(state.function_count)
    print("\n=== CALL GRAPH EDGES ===")
    print(state.call_edge_count)


def log_call_impact(report: CallImpactReport) -> None:
    print("\n=== AFFECTED FUNCTIONS ===")
    print(len(report.affected_functions))
    for fn in sorted(report.affected_functions)[:40]:
        print(f"  fn: {fn}")
    if len(report.affected_functions) > 40:
        print(f"  ... (+{len(report.affected_functions) - 40} more)")
    print("\n=== AFFECTED TESTS ===")
    print(len(report.affected_tests))
    for test in report.affected_tests:
        print(f"  test: {test}")
    print("\n=== PROPAGATION DEPTH ===")
    print(report.propagation_depth)
