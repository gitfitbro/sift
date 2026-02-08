"""Project analyzer orchestrator.

Discovers files, dispatches to the best analyzer (Python AST -> tree-sitter -> basic),
detects dependencies, entry points, and frameworks, and builds a ProjectStructure.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sift.providers.base import AIProvider

from . import ai_analyzer, python_ast_analyzer, tree_sitter_analyzer
from .models import DependencyInfo, FileAnalysis, ProjectStructure, TemplateRecommendation

logger = logging.getLogger(__name__)

# Directories to always skip
SKIP_DIRS: set[str] = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    ".build",
    "target",
    ".idea",
    ".vscode",
    ".vs",
    ".next",
    ".nuxt",
    ".output",
    "vendor",
    "Pods",
    ".terraform",
    ".serverless",
    "coverage",
    ".coverage",
    "htmlcov",
    ".eggs",
    "*.egg-info",
}

# File extensions to analyze
SOURCE_EXTENSIONS: set[str] = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".rb",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".hpp",
    ".cs",
    ".swift",
    ".php",
    ".scala",
    ".lua",
    ".r",
    ".R",
    ".dart",
    ".ex",
    ".exs",
    ".hs",
    ".ml",
    ".sh",
    ".bash",
    ".zsh",
    ".sql",
    ".proto",
    ".zig",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".css",
    ".scss",
    ".html",
    ".htm",
    ".md",
    ".rst",
    ".txt",
}

# Max files to analyze in detail (avoid huge repos)
MAX_ANALYZED_FILES = 500

# Max depth for directory tree rendering
TREE_MAX_DEPTH = 3
TREE_MAX_ENTRIES = 100

# Framework detection: dependency name -> framework label
FRAMEWORK_SIGNATURES: dict[str, str] = {
    # Python
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "typer": "Typer CLI",
    "click": "Click CLI",
    "rich": "Rich",
    "textual": "Textual",
    "pytest": "pytest",
    "sqlalchemy": "SQLAlchemy",
    "pydantic": "Pydantic",
    "celery": "Celery",
    "scrapy": "Scrapy",
    # JavaScript/TypeScript
    "react": "React",
    "react-dom": "React",
    "next": "Next.js",
    "vue": "Vue.js",
    "nuxt": "Nuxt",
    "angular": "Angular",
    "@angular/core": "Angular",
    "express": "Express",
    "nestjs": "NestJS",
    "@nestjs/core": "NestJS",
    "svelte": "Svelte",
    "tailwindcss": "Tailwind CSS",
    "prisma": "Prisma",
    # Go
    "gin-gonic/gin": "Gin",
    "gorilla/mux": "Gorilla Mux",
    "labstack/echo": "Echo",
    # Rust
    "actix-web": "Actix Web",
    "rocket": "Rocket",
    "tokio": "Tokio",
    "serde": "Serde",
    # Ruby
    "rails": "Ruby on Rails",
    "sinatra": "Sinatra",
    # Java
    "spring-boot": "Spring Boot",
}


class ProjectAnalyzer:
    """Orchestrates project analysis using the best available strategy."""

    def analyze(
        self,
        project_path: Path,
        provider: AIProvider | None = None,
    ) -> ProjectStructure:
        """Analyze a project directory and return a ProjectStructure.

        Args:
            project_path: Root directory of the project to analyze.
            provider: Optional AI provider for generating architecture summaries.

        Returns:
            A ProjectStructure with file analyses, dependencies, frameworks, etc.
        """
        project_path = project_path.resolve()
        if not project_path.is_dir():
            raise ValueError(f"Not a directory: {project_path}")

        logger.info("Analyzing project: %s", project_path)

        # Step 1: Discover files
        files = self._discover_files(project_path)
        logger.info("Discovered %d source files", len(files))

        # Step 2: Analyze each file
        analyses = self._analyze_files(files, project_path)

        # Step 3: Compute language stats
        languages: dict[str, int] = {}
        total_lines = 0
        for fa in analyses:
            languages[fa.language] = languages.get(fa.language, 0) + 1
            total_lines += fa.line_count

        # Step 4: Detect dependencies
        dependencies = self._detect_dependencies(project_path)

        # Step 5: Detect entry points
        entry_points = self._detect_entry_points(project_path, analyses)

        # Step 6: Detect frameworks
        dep_names = {d.name.lower() for d in dependencies}
        frameworks = self._detect_frameworks(dep_names)

        # Step 7: Build directory tree
        tree = self._build_directory_tree(project_path)

        structure = ProjectStructure(
            root_path=project_path,
            name=project_path.name,
            languages=languages,
            total_files=len(analyses),
            total_lines=total_lines,
            file_analyses=analyses,
            dependencies=dependencies,
            entry_points=entry_points,
            frameworks_detected=frameworks,
            directory_tree=tree,
        )

        # Step 8: AI architecture summary (optional)
        if provider:
            structure.architecture_summary = ai_analyzer.generate_architecture_summary(
                structure,
                provider,
            )

        return structure

    def recommend_template(
        self,
        structure: ProjectStructure,
        provider: AIProvider | None = None,
    ) -> TemplateRecommendation:
        """Generate a session template recommendation for this project."""
        if provider:
            result = ai_analyzer.generate_template_recommendation(structure, provider)
            if result:
                return result
        return ai_analyzer.heuristic_recommendation(structure)

    def _discover_files(self, root: Path) -> list[Path]:
        """Walk the project tree and collect source files to analyze."""
        files: list[Path] = []
        for item in sorted(root.rglob("*")):
            if not item.is_file():
                continue
            # Skip hidden files
            if any(
                part.startswith(".") and part not in {".env"}
                for part in item.relative_to(root).parts
            ):
                if not any(part == ".github" for part in item.relative_to(root).parts):
                    continue
            # Skip blacklisted directories
            rel_parts = set(item.relative_to(root).parts)
            if rel_parts & SKIP_DIRS:
                continue
            # Only include known source extensions
            if item.suffix not in SOURCE_EXTENSIONS:
                continue
            files.append(item)
            if len(files) >= MAX_ANALYZED_FILES:
                logger.warning("Hit file limit (%d), skipping remaining files", MAX_ANALYZED_FILES)
                break
        return files

    def _analyze_files(self, files: list[Path], root: Path) -> list[FileAnalysis]:
        """Analyze each file using the best available analyzer."""
        analyses: list[FileAnalysis] = []
        for path in files:
            analysis = self._analyze_single_file(path)
            if analysis:
                analyses.append(analysis)
        return analyses

    def _analyze_single_file(self, path: Path) -> FileAnalysis | None:
        """Pick the best analyzer for a file and run it."""
        # Python files: always use stdlib ast for deep analysis
        if python_ast_analyzer.can_analyze(path):
            return python_ast_analyzer.analyze_python_file(path)

        # Other source files: tree-sitter if available, else basic counting
        if tree_sitter_analyzer.can_analyze(path):
            return tree_sitter_analyzer.analyze_file(path)

        # Fallback: basic line counting for recognized extensions
        language = tree_sitter_analyzer.detect_language(path)
        if language == "unknown":
            language = path.suffix.lstrip(".")
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        except OSError:
            line_count = 0
        return FileAnalysis(path=path, language=language, line_count=line_count)

    def _detect_dependencies(self, root: Path) -> list[DependencyInfo]:
        """Detect project dependencies from manifest files."""
        deps: list[DependencyInfo] = []

        # Python: pyproject.toml
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            deps.extend(self._parse_pyproject_toml(pyproject))

        # Python: requirements.txt
        requirements = root / "requirements.txt"
        if requirements.exists():
            deps.extend(self._parse_requirements_txt(requirements))

        # Python: setup.py (basic)
        setup_py = root / "setup.py"
        if setup_py.exists() and not deps:
            deps.append(DependencyInfo(name="(setup.py detected)", source="setup.py"))

        # Node: package.json
        package_json = root / "package.json"
        if package_json.exists():
            deps.extend(self._parse_package_json(package_json))

        # Go: go.mod
        go_mod = root / "go.mod"
        if go_mod.exists():
            deps.extend(self._parse_go_mod(go_mod))

        # Rust: Cargo.toml
        cargo_toml = root / "Cargo.toml"
        if cargo_toml.exists():
            deps.extend(self._parse_cargo_toml(cargo_toml))

        # Ruby: Gemfile
        gemfile = root / "Gemfile"
        if gemfile.exists():
            deps.extend(self._parse_gemfile(gemfile))

        return deps

    def _parse_pyproject_toml(self, path: Path) -> list[DependencyInfo]:
        """Parse dependencies from pyproject.toml."""
        deps: list[DependencyInfo] = []
        try:
            # Python 3.11+ has tomllib; 3.10 needs tomli
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore[no-redef]
                except ImportError:
                    # Manual fallback: just read the raw text
                    return self._parse_pyproject_toml_fallback(path)

            with open(path, "rb") as f:
                data = tomllib.load(f)

            for dep_str in data.get("project", {}).get("dependencies", []):
                name = (
                    dep_str.split(">")[0]
                    .split("<")[0]
                    .split("=")[0]
                    .split("!")[0]
                    .split("[")[0]
                    .strip()
                )
                deps.append(DependencyInfo(name=name, source="pyproject.toml"))
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
        return deps

    def _parse_pyproject_toml_fallback(self, path: Path) -> list[DependencyInfo]:
        """Fallback parser for pyproject.toml when no TOML library is available."""
        deps: list[DependencyInfo] = []
        try:
            content = path.read_text()
            in_deps = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped == "dependencies = [":
                    in_deps = True
                    continue
                if in_deps:
                    if stripped == "]":
                        break
                    name = (
                        stripped.strip('"')
                        .strip("',")
                        .split(">")[0]
                        .split("<")[0]
                        .split("=")[0]
                        .split("[")[0]
                        .strip()
                    )
                    if name:
                        deps.append(DependencyInfo(name=name, source="pyproject.toml"))
        except Exception as e:
            logger.warning("Fallback pyproject.toml parse failed: %s", e)
        return deps

    def _parse_requirements_txt(self, path: Path) -> list[DependencyInfo]:
        """Parse dependencies from requirements.txt."""
        deps: list[DependencyInfo] = []
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                name = (
                    line.split(">")[0]
                    .split("<")[0]
                    .split("=")[0]
                    .split("!")[0]
                    .split("[")[0]
                    .strip()
                )
                if name:
                    deps.append(DependencyInfo(name=name, source="requirements.txt"))
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
        return deps

    def _parse_package_json(self, path: Path) -> list[DependencyInfo]:
        """Parse dependencies from package.json."""
        deps: list[DependencyInfo] = []
        try:
            data = json.loads(path.read_text())
            for section in ("dependencies", "devDependencies"):
                for name, version in data.get(section, {}).items():
                    deps.append(DependencyInfo(name=name, version=version, source="package.json"))
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
        return deps

    def _parse_go_mod(self, path: Path) -> list[DependencyInfo]:
        """Parse dependencies from go.mod."""
        deps: list[DependencyInfo] = []
        try:
            in_require = False
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("require ("):
                    in_require = True
                    continue
                if in_require:
                    if stripped == ")":
                        in_require = False
                        continue
                    parts = stripped.split()
                    if len(parts) >= 2:
                        deps.append(
                            DependencyInfo(name=parts[0], version=parts[1], source="go.mod")
                        )
                elif stripped.startswith("require "):
                    parts = stripped.split()
                    if len(parts) >= 3:
                        deps.append(
                            DependencyInfo(name=parts[1], version=parts[2], source="go.mod")
                        )
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
        return deps

    def _parse_cargo_toml(self, path: Path) -> list[DependencyInfo]:
        """Parse dependencies from Cargo.toml (basic line parsing)."""
        deps: list[DependencyInfo] = []
        try:
            in_deps = False
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped in ("[dependencies]", "[dev-dependencies]"):
                    in_deps = True
                    continue
                if stripped.startswith("[") and in_deps:
                    in_deps = False
                    continue
                if in_deps and "=" in stripped:
                    name = stripped.split("=")[0].strip()
                    if name:
                        deps.append(DependencyInfo(name=name, source="Cargo.toml"))
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
        return deps

    def _parse_gemfile(self, path: Path) -> list[DependencyInfo]:
        """Parse dependencies from Gemfile (basic)."""
        deps: list[DependencyInfo] = []
        try:
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("gem "):
                    parts = stripped.split(",")
                    name = parts[0].replace("gem ", "").strip().strip("'\"")
                    if name:
                        deps.append(DependencyInfo(name=name, source="Gemfile"))
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
        return deps

    def _detect_entry_points(
        self,
        root: Path,
        analyses: list[FileAnalysis],
    ) -> list[str]:
        """Detect likely entry points from common patterns."""
        entry_points: list[str] = []
        candidates = [
            "main.py",
            "__main__.py",
            "app.py",
            "cli.py",
            "manage.py",
            "index.js",
            "index.ts",
            "main.js",
            "main.ts",
            "app.js",
            "app.ts",
            "server.js",
            "server.ts",
            "main.go",
            "cmd/main.go",
            "main.rs",
            "src/main.rs",
            "src/lib.rs",
            "Program.cs",
        ]
        for candidate in candidates:
            if (root / candidate).exists():
                entry_points.append(candidate)

        # Check pyproject.toml for console scripts
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if "[project.scripts]" in content:
                    in_scripts = False
                    for line in content.splitlines():
                        if line.strip() == "[project.scripts]":
                            in_scripts = True
                            continue
                        if in_scripts:
                            if line.strip().startswith("["):
                                break
                            if "=" in line:
                                entry_points.append(line.strip())
            except Exception:
                pass

        # Check for __main__.py in any analyzed Python files
        for fa in analyses:
            if fa.path.name == "__main__.py" and str(fa.path) not in entry_points:
                try:
                    rel = str(fa.path.relative_to(root))
                    entry_points.append(rel)
                except ValueError:
                    pass

        return entry_points

    def _detect_frameworks(self, dep_names: set[str]) -> list[str]:
        """Detect frameworks from dependency names."""
        frameworks: list[str] = []
        seen: set[str] = set()
        for dep_name, framework_label in FRAMEWORK_SIGNATURES.items():
            if dep_name in dep_names and framework_label not in seen:
                frameworks.append(framework_label)
                seen.add(framework_label)
        return sorted(frameworks)

    def _build_directory_tree(self, root: Path, depth: int = 0) -> str:
        """Build an ASCII directory tree (limited depth and entries)."""
        lines: list[str] = []
        self._tree_walk(root, root, lines, depth=0, max_depth=TREE_MAX_DEPTH)
        if len(lines) > TREE_MAX_ENTRIES:
            lines = lines[:TREE_MAX_ENTRIES]
            lines.append("... (truncated)")
        return "\n".join(lines)

    def _tree_walk(
        self,
        root: Path,
        current: Path,
        lines: list[str],
        depth: int,
        max_depth: int,
    ) -> None:
        """Recursively build directory tree lines."""
        if depth > max_depth or len(lines) > TREE_MAX_ENTRIES:
            return

        try:
            entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        prefix = "  " * depth
        for entry in entries:
            name = entry.name
            # Skip hidden and blacklisted
            if name.startswith(".") and name not in {".github", ".env"}:
                continue
            if name in SKIP_DIRS:
                continue

            if entry.is_dir():
                lines.append(f"{prefix}{name}/")
                self._tree_walk(root, entry, lines, depth + 1, max_depth)
            else:
                lines.append(f"{prefix}{name}")
