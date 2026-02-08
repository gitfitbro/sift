# Contributing to Sift

Thank you for your interest in contributing to Sift! This guide will help you get started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/sirrele/sift.git
cd sift

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install in development mode with all dependencies
pip install -e ".[all,dev]"

# Verify the install
sift --help
pytest tests/ -v
```

## Architecture Overview

Sift follows a layered architecture:

```
Consumer Layer    CLI (Typer) | TUI (Textual) | MCP Server
                             |
Service Layer     sift/core/ - SessionService, ExtractionService,
                              BuildService, TemplateService
                             |
Domain Layer      sift/models.py - Session, SessionTemplate, Phase
                             |
Infrastructure    AI Providers (Protocol) | File Storage | PDF
```

**Key principle**: Services never import from `sift.ui`, `sift.cli`, or Typer. Services return dataclasses; consumers handle presentation.

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `sift/core/` | Service layer (business logic) |
| `sift/commands/` | CLI command handlers (thin wrappers) |
| `sift/providers/` | AI provider implementations |
| `sift/tui/` | Textual TUI (optional) |
| `sift/analyzers/` | Project analysis modules |
| `sift/mcp/` | MCP server |
| `sift/telemetry/` | Anonymous telemetry (opt-in) |
| `templates/` | Built-in session templates |
| `tests/` | Test suite |
| `docs/` | Documentation |

## Coding Standards

- **Python 3.10+** - Use modern syntax (type unions with `|`, match statements where appropriate)
- **Formatting**: `ruff format`
- **Linting**: `ruff check`
- **Type checking**: `mypy sift/ --ignore-missing-imports`
- **Line length**: 100 characters
- **Imports**: Standard library, third-party, then local (sorted within groups)

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=sift --cov-report=term-missing

# Specific test file
pytest tests/test_session_service.py -v
```

## Testing Guidelines

- Tests go in `tests/` directory
- Use the `sift_home` fixture from `conftest.py` to isolate tests with temp directories
- Mock AI providers rather than making real API calls
- **Important**: When monkeypatching module constants (like `SESSIONS_DIR`), patch BOTH the source module AND the local import in the service module

## Pull Request Process

1. Fork the repository and create a feature branch
2. Make your changes with tests
3. Ensure all tests pass: `pytest tests/ -v`
4. Ensure code quality: `ruff check sift/ && ruff format --check sift/`
5. Write a clear PR description explaining the change
6. Submit the PR against `main`

## Adding a New AI Provider

Sift uses a plugin system based on setuptools entry points:

1. Create `sift/providers/your_provider.py` implementing the `AIProvider` protocol
2. Register in `pyproject.toml` under `[project.entry-points."sift.providers"]`
3. Or create a separate package with the same entry point group

```python
from sift.providers.base import AIProvider

class YourProvider:
    name = "your-provider"
    model = "default-model"

    def is_available(self) -> bool: ...
    def chat(self, system: str, user: str, max_tokens: int = 4000) -> str: ...
    def transcribe(self, audio_path: Path) -> Optional[str]: ...
```

## Adding a New Template

Place YAML files in the `templates/` directory:

```yaml
name: "My Template"
description: "What this template captures"
phases:
  - id: phase-one
    name: "Phase One"
    prompt: "Describe..."
    extract:
      - id: key_points
        type: list
        prompt: "Extract key points"
outputs:
  - type: yaml
    template: session-config
  - type: markdown
    template: session-summary
```

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Include sift version (`sift doctor show`), Python version, and OS
- For bugs, include steps to reproduce and expected vs actual behavior

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
