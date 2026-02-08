"""Tests for the project analyzer."""

import textwrap
from unittest.mock import MagicMock

import pytest

from sift.analyzers import ai_analyzer, tree_sitter_analyzer
from sift.analyzers.models import (
    DependencyInfo,
    FileAnalysis,
    ProjectStructure,
    TemplateRecommendation,
)
from sift.analyzers.project_analyzer import ProjectAnalyzer
from sift.analyzers.python_ast_analyzer import analyze_python_file, can_analyze

# ── Python AST Analyzer ─────────────────────────────────────────────────


class TestPythonAstAnalyzer:
    def test_analyze_simple_file(self, tmp_path):
        py_file = tmp_path / "example.py"
        py_file.write_text(
            textwrap.dedent('''\
            """Module docstring."""
            import os
            from pathlib import Path

            class MyClass:
                """Class docstring."""
                def method(self):
                    pass

            def standalone_func(x):
                if x > 0:
                    return x
                return -x

            async def async_func():
                pass
        ''')
        )

        result = analyze_python_file(py_file)
        assert result.language == "python"
        assert result.line_count > 0
        assert "MyClass" in result.classes
        assert "method" in result.functions
        assert "standalone_func" in result.functions
        assert "async_func" in result.functions
        assert "os" in result.imports
        assert "pathlib" in result.imports
        assert result.doc_coverage > 0  # class has docstring
        assert result.complexity_score > 0  # has an if branch

    def test_analyze_empty_file(self, tmp_path):
        py_file = tmp_path / "empty.py"
        py_file.write_text("")
        result = analyze_python_file(py_file)
        assert result.language == "python"
        assert result.line_count == 0
        assert result.functions == []
        assert result.classes == []

    def test_analyze_syntax_error(self, tmp_path):
        py_file = tmp_path / "bad.py"
        py_file.write_text("def broken(\n")
        result = analyze_python_file(py_file)
        assert result.language == "python"
        assert result.functions == []  # graceful fallback

    def test_can_analyze(self, tmp_path):
        assert can_analyze(tmp_path / "foo.py")
        assert not can_analyze(tmp_path / "foo.js")
        assert not can_analyze(tmp_path / "foo.txt")


# ── Tree-sitter Analyzer ────────────────────────────────────────────────


class TestTreeSitterAnalyzer:
    def test_detect_language(self, tmp_path):
        assert tree_sitter_analyzer.detect_language(tmp_path / "app.js") == "javascript"
        assert tree_sitter_analyzer.detect_language(tmp_path / "main.go") == "go"
        assert tree_sitter_analyzer.detect_language(tmp_path / "lib.rs") == "rust"
        assert tree_sitter_analyzer.detect_language(tmp_path / "unknown.xyz") == "unknown"

    def test_can_analyze(self, tmp_path):
        assert tree_sitter_analyzer.can_analyze(tmp_path / "app.ts")
        assert tree_sitter_analyzer.can_analyze(tmp_path / "style.css")
        assert not tree_sitter_analyzer.can_analyze(tmp_path / "unknown.xyz")

    def test_analyze_file_basic_fallback(self, tmp_path, monkeypatch):
        """When tree-sitter is not installed, falls back to line counting."""
        monkeypatch.setattr(tree_sitter_analyzer, "_HAS_TREE_SITTER", False)

        js_file = tmp_path / "app.js"
        js_file.write_text("function hello() {\n  console.log('hi');\n}\n")

        result = tree_sitter_analyzer.analyze_file(js_file)
        assert result.language == "javascript"
        assert result.line_count == 3
        assert result.functions == []  # no tree-sitter, just line counting


# ── AI Analyzer ──────────────────────────────────────────────────────────


class TestAIAnalyzer:
    def _make_structure(self, tmp_path):
        return ProjectStructure(
            root_path=tmp_path,
            name="test-project",
            languages={"python": 5, "javascript": 2},
            total_files=7,
            total_lines=500,
            file_analyses=[
                FileAnalysis(
                    path=tmp_path / "main.py",
                    language="python",
                    line_count=100,
                    functions=["main", "run"],
                    complexity_score=5.0,
                ),
            ],
            dependencies=[DependencyInfo(name="flask"), DependencyInfo(name="pytest")],
            entry_points=["main.py"],
            frameworks_detected=["Flask"],
            directory_tree="src/\n  main.py\n  utils.py",
        )

    def test_heuristic_recommendation(self, tmp_path):
        structure = self._make_structure(tmp_path)
        rec = ai_analyzer.heuristic_recommendation(structure)
        assert isinstance(rec, TemplateRecommendation)
        assert rec.template_name == "test-project-review"
        assert len(rec.phases) >= 3  # at least arch, deps, quality
        assert "python" in rec.description.lower()

    def test_generate_architecture_summary_failure(self, tmp_path):
        """When AI call fails, returns empty string."""
        structure = self._make_structure(tmp_path)
        provider = MagicMock()
        provider.chat.side_effect = RuntimeError("API error")

        result = ai_analyzer.generate_architecture_summary(structure, provider)
        assert result == ""

    def test_generate_template_recommendation_success(self, tmp_path):
        """When AI returns valid YAML, parses into TemplateRecommendation."""
        structure = self._make_structure(tmp_path)
        provider = MagicMock()
        provider.chat.return_value = textwrap.dedent("""\
            name: test-project-review
            description: Review template for test-project
            phases:
              - id: architecture
                name: Architecture Review
                prompt: Review the architecture
                capture:
                  - type: text
                    required: true
                extract:
                  - id: patterns
                    type: list
                    prompt: List patterns
        """)

        rec = ai_analyzer.generate_template_recommendation(structure, provider)
        assert rec is not None
        assert rec.template_name == "test-project-review"
        assert len(rec.phases) == 1
        assert rec.phases[0]["id"] == "architecture"

    def test_generate_template_recommendation_bad_yaml(self, tmp_path):
        """When AI returns garbage, falls back to heuristic."""
        structure = self._make_structure(tmp_path)
        provider = MagicMock()
        provider.chat.return_value = "this is not yaml: {{{bad"

        rec = ai_analyzer.generate_template_recommendation(structure, provider)
        # Falls back to heuristic
        assert rec is not None
        assert len(rec.phases) >= 3


# ── Project Analyzer (Orchestrator) ──────────────────────────────────────


class TestProjectAnalyzer:
    def _create_sample_project(self, tmp_path):
        """Create a minimal project structure for testing."""
        project = tmp_path / "my-project"
        project.mkdir()

        # Python files
        (project / "main.py").write_text(
            textwrap.dedent('''\
            """Main entry point."""
            import sys
            from pathlib import Path

            def main():
                print("hello")

            if __name__ == "__main__":
                main()
        ''')
        )

        src = project / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "utils.py").write_text(
            textwrap.dedent("""\
            def helper(x):
                return x + 1
        """)
        )

        # Test file
        tests = project / "tests"
        tests.mkdir()
        (tests / "test_main.py").write_text(
            textwrap.dedent("""\
            def test_main():
                assert True
        """)
        )

        # pyproject.toml
        (project / "pyproject.toml").write_text(
            textwrap.dedent("""\
            [project]
            name = "my-project"
            dependencies = [
                "flask>=2.0",
                "pyyaml>=6.0",
            ]
        """)
        )

        # A JS file
        (project / "script.js").write_text("function greet() { return 'hi'; }\n")

        return project

    def test_analyze_discovers_files(self, tmp_path):
        project = self._create_sample_project(tmp_path)
        analyzer = ProjectAnalyzer()
        structure = analyzer.analyze(project)

        assert structure.name == "my-project"
        assert structure.total_files > 0
        assert structure.total_lines > 0
        assert "python" in structure.languages

    def test_analyze_detects_dependencies(self, tmp_path):
        project = self._create_sample_project(tmp_path)
        analyzer = ProjectAnalyzer()
        structure = analyzer.analyze(project)

        dep_names = [d.name for d in structure.dependencies]
        assert "flask" in dep_names
        assert "pyyaml" in dep_names

    def test_analyze_detects_entry_points(self, tmp_path):
        project = self._create_sample_project(tmp_path)
        analyzer = ProjectAnalyzer()
        structure = analyzer.analyze(project)

        assert "main.py" in structure.entry_points

    def test_analyze_detects_frameworks(self, tmp_path):
        project = self._create_sample_project(tmp_path)
        analyzer = ProjectAnalyzer()
        structure = analyzer.analyze(project)

        assert "Flask" in structure.frameworks_detected

    def test_analyze_builds_directory_tree(self, tmp_path):
        project = self._create_sample_project(tmp_path)
        analyzer = ProjectAnalyzer()
        structure = analyzer.analyze(project)

        assert structure.directory_tree
        assert "main.py" in structure.directory_tree

    def test_analyze_python_files_deeply(self, tmp_path):
        project = self._create_sample_project(tmp_path)
        analyzer = ProjectAnalyzer()
        structure = analyzer.analyze(project)

        # Find the main.py analysis
        main_analysis = next(
            (fa for fa in structure.file_analyses if fa.path.name == "main.py"),
            None,
        )
        assert main_analysis is not None
        assert main_analysis.language == "python"
        assert "main" in main_analysis.functions
        assert "sys" in main_analysis.imports

    def test_analyze_nonexistent_dir(self, tmp_path):
        analyzer = ProjectAnalyzer()
        with pytest.raises(ValueError, match="Not a directory"):
            analyzer.analyze(tmp_path / "nonexistent")

    def test_analyze_skips_gitdir(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        (project / "app.py").write_text("x = 1\n")
        git_dir = project / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("gitconfig\n")

        analyzer = ProjectAnalyzer()
        structure = analyzer.analyze(project)

        paths = [str(fa.path) for fa in structure.file_analyses]
        assert not any(".git" in p for p in paths)

    def test_recommend_template_heuristic(self, tmp_path):
        project = self._create_sample_project(tmp_path)
        analyzer = ProjectAnalyzer()
        structure = analyzer.analyze(project)

        rec = analyzer.recommend_template(structure)
        assert isinstance(rec, TemplateRecommendation)
        assert len(rec.phases) >= 3
        # Should include testing phase since we have test files
        phase_ids = [p["id"] for p in rec.phases]
        assert "testing-strategy" in phase_ids

    def test_recommend_template_with_ai(self, tmp_path):
        project = self._create_sample_project(tmp_path)
        analyzer = ProjectAnalyzer()
        structure = analyzer.analyze(project)

        provider = MagicMock()
        provider.chat.return_value = textwrap.dedent("""\
            name: my-project-review
            description: Code review for my-project
            phases:
              - id: overview
                name: Project Overview
                prompt: Review the project
                capture:
                  - type: text
                    required: true
                extract:
                  - id: summary
                    type: text
                    prompt: Summarize
        """)

        rec = analyzer.recommend_template(structure, provider=provider)
        assert rec.template_name == "my-project-review"
        assert len(rec.phases) == 1


# ── Dependency Parsers ───────────────────────────────────────────────────


class TestDependencyParsers:
    def test_parse_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"react": "^18.0"}, "devDependencies": {"jest": "^29.0"}}'
        )

        analyzer = ProjectAnalyzer()
        deps = analyzer._parse_package_json(tmp_path / "package.json")
        names = [d.name for d in deps]
        assert "react" in names
        assert "jest" in names

    def test_parse_requirements_txt(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask>=2.0\nrequests\n# comment\npytest>=7.0\n")

        analyzer = ProjectAnalyzer()
        deps = analyzer._parse_requirements_txt(tmp_path / "requirements.txt")
        names = [d.name for d in deps]
        assert "flask" in names
        assert "requests" in names
        assert "pytest" in names

    def test_parse_go_mod(self, tmp_path):
        (tmp_path / "go.mod").write_text(
            textwrap.dedent("""\
            module example.com/myapp

            go 1.21

            require (
                github.com/gin-gonic/gin v1.9.1
                github.com/stretchr/testify v1.8.4
            )
        """)
        )

        analyzer = ProjectAnalyzer()
        deps = analyzer._parse_go_mod(tmp_path / "go.mod")
        names = [d.name for d in deps]
        assert "github.com/gin-gonic/gin" in names

    def test_parse_cargo_toml(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text(
            textwrap.dedent("""\
            [package]
            name = "myapp"

            [dependencies]
            serde = "1.0"
            tokio = { version = "1.0", features = ["full"] }
        """)
        )

        analyzer = ProjectAnalyzer()
        deps = analyzer._parse_cargo_toml(tmp_path / "Cargo.toml")
        names = [d.name for d in deps]
        assert "serde" in names
        assert "tokio" in names

    def test_parse_gemfile(self, tmp_path):
        (tmp_path / "Gemfile").write_text("gem 'rails', '~> 7.0'\ngem 'puma'\n")

        analyzer = ProjectAnalyzer()
        deps = analyzer._parse_gemfile(tmp_path / "Gemfile")
        names = [d.name for d in deps]
        assert "rails" in names
        assert "puma" in names
