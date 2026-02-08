"""Tests for AnalysisService - analysis-session integration."""

import pytest
import yaml

from sift.analyzers.models import DependencyInfo, FileAnalysis, ProjectStructure
from sift.core.analysis_service import (
    AnalysisService,
    serialize_analysis_context,
    serialize_analysis_text,
)
from sift.models import Session


@pytest.fixture
def sample_structure(tmp_path):
    """Create a ProjectStructure for testing serialization."""
    return ProjectStructure(
        root_path=tmp_path,
        name="test-project",
        languages={"python": 5, "javascript": 3},
        total_files=8,
        total_lines=1200,
        file_analyses=[
            FileAnalysis(
                path=tmp_path / "main.py",
                language="python",
                line_count=200,
                functions=["main", "setup", "run"],
                classes=["App"],
                complexity_score=4.5,
                doc_coverage=0.67,
            ),
            FileAnalysis(
                path=tmp_path / "utils.py",
                language="python",
                line_count=100,
                functions=["helper"],
                complexity_score=1.2,
            ),
        ],
        dependencies=[
            DependencyInfo(name="flask", version=">=2.0", source="pyproject.toml"),
            DependencyInfo(name="pyyaml", version="^6.0", source="pyproject.toml"),
        ],
        entry_points=["main.py"],
        frameworks_detected=["Flask"],
        directory_tree="main.py\nutils.py\ntemplates/",
        architecture_summary="A Flask web application with CLI tooling.",
    )


@pytest.fixture
def sample_project(tmp_path):
    """Create a minimal project directory for analysis."""
    project = tmp_path / "test-project"
    project.mkdir()
    (project / "main.py").write_text('"""Main."""\ndef main():\n    pass\n')
    (project / "pyproject.toml").write_text(
        '[project]\nname = "test-project"\ndependencies = ["flask"]\n'
    )
    return project


@pytest.fixture
def analysis_template_path(sift_home):
    """Create a template with architecture/dependency phases for auto-population testing."""
    template_data = {
        "name": "Analysis Test Template",
        "description": "Template with phases matching analysis keywords",
        "phases": [
            {
                "id": "architecture-overview",
                "name": "Architecture Overview",
                "prompt": "Review the architecture.",
                "capture": [{"type": "text", "required": True}],
                "extract": [
                    {"id": "patterns", "type": "list", "prompt": "List patterns used."},
                ],
            },
            {
                "id": "dependency-audit",
                "name": "Dependency Audit",
                "prompt": "Audit the dependencies.",
                "capture": [{"type": "text", "required": True}],
                "extract": [
                    {"id": "risks", "type": "list", "prompt": "List dependency risks."},
                ],
            },
            {
                "id": "action-items",
                "name": "Action Items",
                "prompt": "Define next steps.",
                "capture": [{"type": "text", "required": True}],
                "extract": [
                    {"id": "actions", "type": "list", "prompt": "List action items."},
                ],
            },
        ],
        "outputs": [
            {"type": "yaml", "template": "session-config"},
        ],
    }
    path = sift_home / "templates" / "analysis-test-template.yaml"
    with open(path, "w") as f:
        yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)
    return path


# ── Serialization Tests ─────────────────────────────────────────────────


class TestSerializeAnalysisText:
    def test_includes_project_name(self, sample_structure):
        text = serialize_analysis_text(sample_structure)
        assert "test-project" in text

    def test_includes_overview_stats(self, sample_structure):
        text = serialize_analysis_text(sample_structure)
        assert "Total files: 8" in text
        assert "1,200" in text

    def test_includes_languages(self, sample_structure):
        text = serialize_analysis_text(sample_structure)
        assert "python" in text
        assert "javascript" in text

    def test_includes_frameworks(self, sample_structure):
        text = serialize_analysis_text(sample_structure)
        assert "Flask" in text

    def test_includes_entry_points(self, sample_structure):
        text = serialize_analysis_text(sample_structure)
        assert "main.py" in text

    def test_includes_dependencies(self, sample_structure):
        text = serialize_analysis_text(sample_structure)
        assert "flask" in text
        assert "pyyaml" in text

    def test_includes_directory_tree(self, sample_structure):
        text = serialize_analysis_text(sample_structure)
        assert "Directory Structure" in text
        assert "templates/" in text

    def test_includes_architecture_summary(self, sample_structure):
        text = serialize_analysis_text(sample_structure)
        assert "Architecture Summary" in text
        assert "Flask web application" in text

    def test_includes_complexity_hotspots(self, sample_structure):
        text = serialize_analysis_text(sample_structure)
        assert "Complexity Hotspots" in text
        assert "complexity=4.5" in text

    def test_handles_empty_structure(self, tmp_path):
        structure = ProjectStructure(root_path=tmp_path, name="empty")
        text = serialize_analysis_text(structure)
        assert "empty" in text
        assert "Total files: 0" in text


class TestSerializeAnalysisContext:
    def test_returns_dict(self, sample_structure):
        ctx = serialize_analysis_context(sample_structure)
        assert isinstance(ctx, dict)
        assert ctx["project_name"] == "test-project"

    def test_includes_all_fields(self, sample_structure):
        ctx = serialize_analysis_context(sample_structure)
        assert ctx["total_files"] == 8
        assert ctx["total_lines"] == 1200
        assert ctx["frameworks"] == ["Flask"]
        assert ctx["entry_points"] == ["main.py"]
        assert len(ctx["dependencies"]) == 2

    def test_is_yaml_serializable(self, sample_structure):
        ctx = serialize_analysis_context(sample_structure)
        dumped = yaml.dump(ctx)
        loaded = yaml.safe_load(dumped)
        assert loaded["project_name"] == "test-project"
        assert loaded["frameworks"] == ["Flask"]

    def test_limits_dependencies(self, tmp_path):
        deps = [DependencyInfo(name=f"dep-{i}") for i in range(50)]
        structure = ProjectStructure(root_path=tmp_path, name="big", dependencies=deps)
        ctx = serialize_analysis_context(structure)
        assert len(ctx["dependencies"]) == 30


# ── AnalysisService Tests ────────────────────────────────────────────────


class TestCaptureAnalysis:
    def test_captures_analysis_as_transcript(self, sample_session, sample_project):
        svc = AnalysisService()
        svc.capture_analysis("test-session", "gather-info", sample_project)

        s = Session.load("test-session")
        assert s.phases["gather-info"].status == "transcribed"

        transcript_path = s.phase_dir("gather-info") / "transcript.txt"
        transcript = transcript_path.read_text()
        assert "test-project" in transcript

    def test_stores_analysis_context(self, sample_session, sample_project):
        svc = AnalysisService()
        svc.capture_analysis("test-session", "gather-info", sample_project)

        s = Session.load("test-session")
        analysis_path = s.dir / "analysis.yaml"
        assert analysis_path.exists()

        with open(analysis_path) as f:
            ctx = yaml.safe_load(f)
        assert ctx["project_name"] == "test-project"

    def test_append_mode(self, sample_session, sample_project):
        svc = AnalysisService()
        from sift.core.extraction_service import ExtractionService

        ext_svc = ExtractionService()
        ext_svc.capture_text("test-session", "gather-info", "Existing content.")

        svc.capture_analysis("test-session", "gather-info", sample_project, append=True)

        s = Session.load("test-session")
        transcript_path = s.phase_dir("gather-info") / "transcript.txt"
        transcript = transcript_path.read_text()
        assert "Existing content." in transcript
        assert "test-project" in transcript


class TestGetAnalysisContext:
    def test_returns_none_when_missing(self, sample_session):
        svc = AnalysisService()
        assert svc.get_analysis_context("test-session") is None

    def test_returns_context_when_present(self, sample_session):
        svc = AnalysisService()
        s = Session.load("test-session")
        ctx = {"project_name": "test", "languages": {"python": 5}}
        with open(s.dir / "analysis.yaml", "w") as f:
            yaml.dump(ctx, f)

        loaded = svc.get_analysis_context("test-session")
        assert loaded["project_name"] == "test"
        assert loaded["languages"]["python"] == 5


class TestPopulateMatchingPhases:
    def test_populates_architecture_phase(self, analysis_template_path, sample_project):
        from sift.core.session_service import SessionService

        svc = SessionService()
        detail = svc.create_session("analysis-test-template", name="pop-test")

        analysis_svc = AnalysisService()
        structure = ProjectStructure(
            root_path=sample_project,
            name="test-project",
            languages={"python": 1},
            total_files=1,
            total_lines=10,
            dependencies=[DependencyInfo(name="flask")],
        )
        populated = analysis_svc._populate_matching_phases("pop-test", structure)

        assert "architecture-overview" in populated
        assert "dependency-audit" in populated
        # "action-items" should NOT be auto-populated (no matching keywords)
        assert "action-items" not in populated

    def test_skips_non_pending_phases(self, analysis_template_path, sample_project):
        from sift.core.extraction_service import ExtractionService
        from sift.core.session_service import SessionService

        svc = SessionService()
        svc.create_session("analysis-test-template", name="skip-test")

        # Pre-populate architecture phase manually
        ext_svc = ExtractionService()
        ext_svc.capture_text("skip-test", "architecture-overview", "Already populated.")

        analysis_svc = AnalysisService()
        structure = ProjectStructure(
            root_path=sample_project,
            name="test-project",
            languages={"python": 1},
            total_files=1,
            total_lines=10,
        )
        populated = analysis_svc._populate_matching_phases("skip-test", structure)

        assert "architecture-overview" not in populated


# ── Context Injection Tests ──────────────────────────────────────────────


class TestExtractionContextInjection:
    def test_injection_methods_on_extraction_service(self, sample_session):
        from sift.core.extraction_service import ExtractionService

        ext_svc = ExtractionService()
        s = Session.load("test-session")

        # No analysis file -> returns None
        assert ext_svc._load_analysis_context(s) is None

        # Write analysis file
        ctx = {
            "project_name": "test-project",
            "languages": {"python": 5},
            "frameworks": ["Flask"],
            "entry_points": ["main.py"],
            "architecture_summary": "A Flask app.",
        }
        with open(s.dir / "analysis.yaml", "w") as f:
            yaml.dump(ctx, f)

        loaded = ext_svc._load_analysis_context(s)
        assert loaded["project_name"] == "test-project"

    def test_inject_analysis_context_prepends(self, sample_session):
        from sift.core.extraction_service import ExtractionService

        ext_svc = ExtractionService()
        analysis = {
            "project_name": "test-project",
            "languages": {"python": 5},
            "frameworks": ["Flask"],
            "entry_points": ["main.py"],
            "architecture_summary": "A Flask app.",
        }

        result = ext_svc._inject_analysis_context("Previous phase data here.", analysis)
        assert result.startswith("Project context (test-project):")
        assert "Flask" in result
        assert "Previous phase data here." in result

    def test_inject_analysis_context_empty_existing(self, sample_session):
        from sift.core.extraction_service import ExtractionService

        ext_svc = ExtractionService()
        analysis = {
            "project_name": "test-project",
            "languages": {},
        }

        result = ext_svc._inject_analysis_context("", analysis)
        assert "test-project" in result


class TestAnalyzeAndCreateSession:
    def test_one_shot_creates_session(self, sample_project, sift_home):
        svc = AnalysisService()
        result = svc.analyze_and_create_session(sample_project)

        assert result.session_detail is not None
        assert result.analysis_path.exists()
        assert result.template_name
        assert len(result.populated_phases) >= 1

        # Verify session exists and has analysis.yaml
        s = Session.load(result.session_detail.name)
        assert (s.dir / "analysis.yaml").exists()


class TestCreateSessionWithAnalysis:
    def test_two_step_creates_session(self, analysis_template_path, sample_project):
        svc = AnalysisService()
        result = svc.create_session_with_analysis(
            "analysis-test-template", sample_project, session_name="two-step-test"
        )

        assert result.session_detail.name == "two-step-test"
        assert result.analysis_path.exists()

        # Architecture phase should be auto-populated
        s = Session.load("two-step-test")
        assert s.phases["architecture-overview"].status == "transcribed"
