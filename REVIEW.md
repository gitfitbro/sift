# Critical Project Review: SIFT

**Reviewer:** Claude (automated review)
**Date:** 2026-02-12
**Version Reviewed:** 0.2.0 (Beta)
**Scope:** Architecture, code quality, security, design decisions

---

## Project Summary

SIFT is a CLI tool and MCP server (~12,600 LOC Python, 68 source files) that captures unstructured input from conversations, interviews, and domain expertise — then uses AI extraction (Claude, Gemini, Ollama) to produce structured output (YAML configs, markdown summaries, reports). Licensed under MIT, targeting Python 3.10+.

---

## What Works Well

### Architecture
- Clean layered design: CLI/TUI/MCP consumers → command handlers → service layer → domain models → infrastructure
- Services never import from UI layers — proper separation of concerns
- `AIProvider` Protocol enables genuine pluggability without inheritance chains
- Entry-point-based plugin discovery is the right extensibility mechanism

### Problem-Domain Fit
- Extracting structured knowledge from unstructured conversations is a real pain point
- 10 built-in templates (discovery calls, architecture review, workflow extraction) show domain understanding
- Multiple consumption surfaces (CLI, TUI, MCP, OpenClawd) give the tool reach

### Testing & CI
- 24 test files / ~4,000 lines with proper fixture isolation (temp directories)
- Mocked AI providers, integration test markers
- CI matrix: Python 3.10–3.13 with lint, type checking, and build verification

### Dependency Management
- Optional extras (`[tui]`, `[mcp]`, `[pdf]`, `[analysis]`) keep base install lean
- No mandatory heavy dependencies beyond Typer/Rich/PyYAML/Jinja2
- Minimum version pinning for reproducibility

---

## Issues Found

### 1. Broad Exception Handling (30+ instances)

Bare `except Exception:` appears across the codebase — in `sift/core/session_service.py`, `sift/plugins.py`, `sift/tui/widgets/capture_form.py`, `sift/telemetry/service.py`, and others. This swallows `TypeError`, `AttributeError`, `KeyError` — the bugs you want to surface during development. The custom exception hierarchy in `sift/errors.py` is well-designed but underutilized.

**Recommendation:** Replace with specific exception types at all 30+ call sites.

### 2. Missing Input Validation

- **Phase dependencies** (`depends_on` in `sift/models.py`) stored but never validated for cycles — could cause infinite loops
- **No file size limits** on PDF or audio input — could exhaust memory
- **No token limit checking** before sending transcripts to AI providers — long transcripts silently exceed context windows
- **Credentials file parsing** in `sift/core/secrets.py` uses naive `line.partition("=")` — values containing `=` silently truncated

**Recommendation:** Add validation layer for dependencies, file sizes, token budgets, and credential parsing.

### 3. Service Layer Coupling

Services instantiate their own dependencies internally:

```python
# session_service.py
def __init__(self):
    self._template_svc = TemplateService()
```

This makes testing harder (requires monkey-patching) and creates implicit coupling. Inconsistent with the Protocol-based abstraction used for providers.

**Recommendation:** Accept dependencies in `__init__` with production defaults; pass explicit mocks in tests.

### 4. Provider Code Duplication

All three providers repeat the same initialization pattern (key retrieval, model config lookup, error mapping) — roughly 40-60 duplicated lines that grow with each new provider.

**Recommendation:** Extract a `BaseProvider` class or shared factory.

### 5. Thread Safety Absent

Module-level globals (`_active_provider`, module-level service singletons) are not thread-safe. Acceptable for single-user CLI but problematic for the async MCP server or future library use.

**Recommendation:** Document the limitation; consider thread-local storage.

### 6. No File Locking or Atomic Writes

Session state persisted as YAML with no file locking. `Session.save()` does full writes without atomic patterns (write-to-temp-then-rename). Multiple processes could corrupt data.

**Recommendation:** Use atomic writes (`tempfile` + `os.replace()`) for `Session.save()`.

### 7. TUI Scope Concerns

The `sift/tui/` module adds meaningful surface area and dependency weight for a v0.2.0 beta. Three UIs (CLI, TUI, MCP) spread maintenance effort thin. TUI test coverage appears lighter than other modules.

**Recommendation:** Defer TUI or invest in full feature parity and testing.

### 8. Incomplete Internationalization

`sift/i18n.py` and `sift/locales/` exist but i18n isn't wired through most of the codebase. User-facing strings are hardcoded English. Adds maintenance burden without delivering value.

**Recommendation:** Remove scaffolding until ready to implement fully, or complete the integration.

---

## Design Observations

- **File-based storage is the right call** for this stage. YAML sessions avoid database dependencies and make debugging trivial. Schema versioning and migration service show foresight.
- **The template system is the core value proposition.** Template validation is weak though — version checking exists but no schema validation for content. Malformed templates fail at runtime.
- **The project analyzer** creates a second axis of complexity. SIFT is both a "conversation capture tool" and a "code analysis tool." Consider whether the analyzer belongs in core or should be a plugin.

---

## Security Notes

- Secure credential file permissions (0600) — good
- `yaml.safe_load()` used consistently — good
- No `eval()`, `exec()`, or `pickle` on untrusted data — good
- Subprocess calls use list arguments (no shell injection) — good
- Missing: file size limits, PDF content validation, error handling on subprocess failures

---

## Scoring

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Architecture | A | Clean layers, proper separation |
| Error Handling | A- | Good hierarchy, too many broad catches |
| Code Organization | A | Well-modularized |
| Naming Conventions | A- | Consistent, minor abbreviations |
| DRY | B | Provider duplication |
| Dead Code | A | Clean |
| API Design | B+ | Needs consistency, DI |
| State Management | B+ | Sound but not thread-safe |
| Performance | A- | Efficient for CLI, some unbounded ops |
| Edge Cases | B- | Many handled, missing cycle/concurrency checks |
| Security | B+ | Good practices, needs input validation |
| Testing | A- | Solid coverage, could expand edge cases |
| Documentation | A- | Comprehensive, some gaps |
| **Overall** | **B+** | **Solid foundation, needs hardening for 1.0** |

---

## Prioritized Recommendations

1. Replace broad `except Exception` with specific types (30+ sites)
2. Add input validation (cycle detection, file size limits, token budgets)
3. Use dependency injection for services
4. Extract `BaseProvider` to eliminate duplication
5. Add atomic file writes for `Session.save()`
6. Decide on TUI: invest properly or defer
7. Remove or complete i18n scaffolding
8. Add template schema validation at load time
