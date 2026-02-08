"""Multi-language AST analyzer using tree-sitter.

Supports 40+ languages when tree-sitter is installed.
Falls back to basic line-counting analysis when unavailable.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .models import FileAnalysis

logger = logging.getLogger(__name__)

# Language extension mapping
LANGUAGE_MAP: dict[str, str] = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "c_sharp",
    ".swift": "swift",
    ".php": "php",
    ".scala": "scala",
    ".lua": "lua",
    ".r": "r",
    ".R": "r",
    ".dart": "dart",
    ".ex": "elixir",
    ".exs": "elixir",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".css": "css",
    ".scss": "css",
    ".html": "html",
    ".htm": "html",
    ".sql": "sql",
    ".proto": "protobuf",
    ".zig": "zig",
}

# Node types that represent function/method definitions per language
FUNCTION_NODE_TYPES: dict[str, set[str]] = {
    "javascript": {"function_declaration", "method_definition", "arrow_function"},
    "typescript": {"function_declaration", "method_definition", "arrow_function"},
    "go": {"function_declaration", "method_declaration"},
    "rust": {"function_item"},
    "java": {"method_declaration", "constructor_declaration"},
    "ruby": {"method", "singleton_method"},
    "c": {"function_definition"},
    "cpp": {"function_definition"},
    "c_sharp": {"method_declaration", "constructor_declaration"},
    "swift": {"function_declaration"},
}

CLASS_NODE_TYPES: dict[str, set[str]] = {
    "javascript": {"class_declaration"},
    "typescript": {"class_declaration"},
    "java": {"class_declaration", "interface_declaration"},
    "ruby": {"class", "module"},
    "c_sharp": {"class_declaration", "interface_declaration"},
    "swift": {"class_declaration", "protocol_declaration"},
    "rust": {"struct_item", "enum_item", "impl_item"},
    "go": {"type_declaration"},
}

IMPORT_NODE_TYPES: dict[str, set[str]] = {
    "javascript": {"import_statement"},
    "typescript": {"import_statement"},
    "go": {"import_declaration"},
    "rust": {"use_declaration"},
    "java": {"import_declaration"},
    "ruby": {"call"},  # require/require_relative
    "c": {"preproc_include"},
    "cpp": {"preproc_include"},
    "c_sharp": {"using_directive"},
    "swift": {"import_declaration"},
}


def _try_tree_sitter() -> bool:
    """Check if tree-sitter is available."""
    try:
        import tree_sitter_languages  # noqa: F401
        return True
    except ImportError:
        return False


_HAS_TREE_SITTER: bool | None = None


def is_available() -> bool:
    """Return True if tree-sitter is installed."""
    global _HAS_TREE_SITTER
    if _HAS_TREE_SITTER is None:
        _HAS_TREE_SITTER = _try_tree_sitter()
    return _HAS_TREE_SITTER


def can_analyze(path: Path) -> bool:
    """Return True if this analyzer can handle the given file."""
    return path.suffix in LANGUAGE_MAP


def detect_language(path: Path) -> str:
    """Detect programming language from file extension."""
    return LANGUAGE_MAP.get(path.suffix, "unknown")


def analyze_file(path: Path) -> FileAnalysis:
    """Analyze a source file using tree-sitter if available, else basic counting.

    When tree-sitter is available, extracts functions, classes, and imports
    from the AST. Otherwise falls back to line counting with language detection.
    """
    language = detect_language(path)

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.warning("Could not read %s: %s", path, e)
        return FileAnalysis(path=path, language=language, line_count=0)

    line_count = source.count("\n") + (1 if source and not source.endswith("\n") else 0)

    if not is_available():
        return FileAnalysis(path=path, language=language, line_count=line_count)

    return _analyze_with_tree_sitter(path, language, source, line_count)


def _analyze_with_tree_sitter(
    path: Path, language: str, source: str, line_count: int,
) -> FileAnalysis:
    """Perform tree-sitter AST analysis."""
    try:
        from tree_sitter_languages import get_parser
    except ImportError:
        return FileAnalysis(path=path, language=language, line_count=line_count)

    try:
        parser = get_parser(language)
    except Exception:
        # Language not supported by installed tree-sitter grammars
        return FileAnalysis(path=path, language=language, line_count=line_count)

    tree = parser.parse(source.encode("utf-8"))
    root = tree.root_node

    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []

    fn_types = FUNCTION_NODE_TYPES.get(language, set())
    cls_types = CLASS_NODE_TYPES.get(language, set())
    imp_types = IMPORT_NODE_TYPES.get(language, set())

    def _walk(node):
        if node.type in fn_types:
            name_node = node.child_by_field_name("name")
            if name_node:
                functions.append(name_node.text.decode("utf-8"))
        elif node.type in cls_types:
            name_node = node.child_by_field_name("name")
            if name_node:
                classes.append(name_node.text.decode("utf-8"))
        elif node.type in imp_types:
            imports.append(node.text.decode("utf-8")[:120])  # Truncate long imports

        for child in node.children:
            _walk(child)

    _walk(root)

    return FileAnalysis(
        path=path,
        language=language,
        line_count=line_count,
        functions=functions,
        classes=classes,
        imports=imports,
    )
