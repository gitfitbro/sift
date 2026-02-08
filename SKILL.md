---
name: sift
description: Structured session capture & AI extraction
version: 0.2.0
author: sirrele
---

# Sift - Structured Session Capture & AI Extraction

Sift is a CLI tool and MCP server for running structured capture sessions. It guides you through multi-phase workflows (discovery calls, architecture reviews, workflow extraction) where each phase captures content, transcribes audio, and extracts structured data using AI.

## Setup

```bash
# Install sift with MCP support
pip install "sift-cli[mcp]"

# Register as MCP server for Claude Code
claude mcp add sift -- sift-mcp
```

## MCP Tools

### `sift_list_templates`
List all available session templates with descriptions and phase counts.

```
sift_list_templates()
```

### `sift_create_session`
Create a new session from a template. Supports `+` syntax for combining templates.

```
sift_create_session(template="discovery-call")
sift_create_session(template="discovery-call+workflow-extraction", name="my-session")
```

### `sift_list_sessions`
List all sessions with their status (active, complete) and phase progress.

```
sift_list_sessions()
```

### `sift_session_status`
Get detailed status for a session including all phases and next suggested action.

```
sift_session_status(session_name="2025-01-15_discovery-call")
```

### `sift_capture_text`
Capture text content for a specific session phase.

```
sift_capture_text(
    session_name="my-session",
    phase_id="gather-info",
    text="The client uses a microservices architecture with 12 services..."
)
```

### `sift_extract_phase`
Extract structured data from a phase transcript using AI. Requires the phase to have captured text first.

```
sift_extract_phase(session_name="my-session", phase_id="gather-info")
```

### `sift_build_outputs`
Generate output files (YAML config, markdown summary, consolidated data) from a session.

```
sift_build_outputs(session_name="my-session")
sift_build_outputs(session_name="my-session", format="markdown")
```

### `sift_analyze_project`
Analyze a software project's structure, languages, dependencies, and frameworks.

```
sift_analyze_project(project_path="/path/to/project")
sift_analyze_project(project_path="/path/to/project", include_ai_summary=True)
```

### `sift_export_session`
Export all session data (metadata, transcripts, extracted data) as JSON.

```
sift_export_session(session_name="my-session")
```

## Common Workflows

### Run a discovery call session
1. `sift_list_templates()` - see available templates
2. `sift_create_session(template="discovery-call")` - create session
3. `sift_capture_text(session_name=..., phase_id=..., text=...)` - capture notes for each phase
4. `sift_extract_phase(session_name=..., phase_id=...)` - extract structured data per phase
5. `sift_build_outputs(session_name=...)` - generate final outputs

### Analyze a project and create a tailored session
1. `sift_analyze_project(project_path=".")` - understand the codebase
2. `sift_create_session(template="ghost-architecture")` - create appropriate session
3. Capture findings and extract structured data phase by phase

## Templates

Sift ships with these built-in templates:
- **discovery-call** - Client discovery and requirements gathering
- **ghost-architecture** - Reverse-engineer undocumented system architecture
- **last-mile-assessment** - Evaluate project readiness for launch
- **workflow-extraction** - Document and optimize team workflows
- **infra-workflow-mapping** - Map infrastructure, dev tooling, and deployment pipelines
