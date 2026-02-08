"""Python AST analyzer using stdlib ast module.

Provides deep analysis of Python files: functions, classes, imports,
docstring coverage, and a simple complexity score.
"""
from __future__ import annotations

import ast
import logging
from pathlib import Path

from .models import FileAnalysis

logger = logging.getLogger(__name__)


def analyze_python_file(path: Path) -> FileAnalysis:
    """Analyze a Python file using the stdlib ast module.

    Returns a FileAnalysis with functions, classes, imports, doc coverage,
    and a basic complexity score (branch count).
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.warning("Could not read %s: %s", path, e)
        return FileAnalysis(path=path, language="python", line_count=0)

    line_count = source.count("\n") + (1 if source and not source.endswith("\n") else 0)

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        logger.warning("Syntax error in %s: %s", path, e)
        return FileAnalysis(path=path, language="python", line_count=line_count)

    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []
    documented = 0
    total_documentable = 0
    branch_count = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.append(node.name)
            total_documentable += 1
            if ast.get_docstring(node):
                documented += 1
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
            total_documentable += 1
            if ast.get_docstring(node):
                documented += 1
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, ast.If | ast.For | ast.While | ast.Try
                         | ast.With | ast.ExceptHandler):
            branch_count += 1

    doc_coverage = (documented / total_documentable) if total_documentable > 0 else 0.0
    # Normalize complexity: branches per 100 lines
    complexity = (branch_count / max(line_count, 1)) * 100

    return FileAnalysis(
        path=path,
        language="python",
        line_count=line_count,
        functions=functions,
        classes=classes,
        imports=imports,
        complexity_score=round(complexity, 2),
        doc_coverage=round(doc_coverage, 2),
    )


def can_analyze(path: Path) -> bool:
    """Return True if this analyzer can handle the given file."""
    return path.suffix == ".py"
