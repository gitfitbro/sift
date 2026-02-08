# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2025-02-07

### Added
- **Telemetry**: Opt-in anonymous telemetry with OpenTelemetry (Phase 10)
  - Consent manager with GDPR/CCPA compliance
  - `sift telemetry status/enable/disable` commands
  - Environment variable override: `SIFT_TELEMETRY=disabled`
- **Accessibility & Plain Output** (Phase 13)
  - `--plain` global flag for colorless, panelless ASCII output
  - `--json` global flag for machine-readable JSON output
  - Auto-detects piped stdout and enables plain mode
  - `--verbose/-v` flag for configurable log verbosity
- **Docker Support** (Phase 14)
  - Production Dockerfile with FFmpeg for audio processing
  - docker-compose.yml for development with MCP server service
  - .dockerignore for clean builds
- **Internationalization** (Phase 15)
  - gettext-based i18n foundation (`sift/i18n.py`)
  - POT template for community translations
  - `SIFT_LANG` environment variable support
- **Open Source Readiness** (Phase 6)
  - CONTRIBUTING.md with development guide
  - CODE_OF_CONDUCT.md (Contributor Covenant)
  - LICENSE (MIT)
  - GitHub Actions CI/CD (test matrix, lint, publish)
  - ruff.toml for consistent code formatting
- **Session & Template Export/Import** (Phase 12)
  - `sift export session/template` commands
  - `sift import-data session/template` commands
  - ZIP archive format with manifest
- **Plugin System** (Phase 9)
  - Setuptools entry points for providers, analyzers, formatters
  - `sift plugins` command for discovery
- **Ollama Provider** (Phase 8)
  - Local AI via Ollama REST API
  - `sift models --provider ollama` for model listing
- **Configuration & Secrets** (Phase 7)
  - Layered config: CLI flags > env vars > project > global > defaults
  - Secure API key storage with `sift config set-key`
- **Schema Versioning & Diagnostics** (Phase 11)
  - Schema version fields on templates and sessions
  - `sift doctor` diagnostic command
- **MCP Server** (Phase 5)
  - 9 tools exposed via Model Context Protocol
  - `sift-mcp` console script entry point
- **Project Analyzer** (Phase 4)
  - `sift analyze` with Python AST and tree-sitter support
  - AI-powered architecture summaries
- **Textual TUI** (Phase 3)
  - Interactive session runner and workspace
  - Graceful fallback to Rich when Textual not installed
- **Shell Completion** (Phase 2)
  - Tab completion for sessions, templates, phases, providers

## [0.1.0] - 2024-12-01

### Added
- Initial release
- Core service layer (SessionService, ExtractionService, BuildService, TemplateService)
- AI Provider Protocol with Anthropic and Gemini support
- CLI commands for session management, phase processing, and output generation
- Rich terminal UI with themed panels and pipeline views
- Built-in templates: workflow-extraction, discovery-call, ghost-architecture, last-mile-assessment
- PDF document import and analysis
- Test suite with isolated fixtures
