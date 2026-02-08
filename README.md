# sift

[![CI](https://github.com/sirrele/sift/actions/workflows/ci.yml/badge.svg)](https://github.com/sirrele/sift/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/sirrele/sift/pkgs/container/sift)

A domain-agnostic CLI for running structured sessions, capturing audio/transcripts, extracting structured data with AI, and generating configs.

**Use it for:** mentorship sessions, discovery calls, user interviews, workshops, or any conversation that needs structured outputs.

## Quick Start

```bash
# Install
pip install sift-cli[all]

# Or from source
git clone https://github.com/sirrele/sift.git && cd sift
pip install -e ".[all]"

# Enable AI features
sift config set-key anthropic YOUR_API_KEY

# List available templates
sift template list

# Create and run a session
sift new workflow-extraction --name my-session
sift run my-session
```

## How It Works

### The Pipeline
```
Audio/Text --> Transcribe --> Extract --> Build Outputs
```

1. **Templates** define the structure of any session type (YAML files)
2. **Sessions** capture data through phases (audio, text, PDF)
3. **AI extraction** pulls structured data from transcripts
4. **Outputs** generate configs, summaries, and reports

## Commands

### Session Workflow
| Command | Description |
|---------|-------------|
| `sift new <template> --name <name>` | Create a session from a template |
| `sift run <session>` | Interactive guided walkthrough (TUI or Rich) |
| `sift status <session>` | Show session progress |
| `sift ls` | List all sessions |
| `sift open <session>` | Interactive session workspace |
| `sift import <session> --file <pdf>` | Import multi-phase document |

### Phase Operations
| Command | Description |
|---------|-------------|
| `sift phase capture <session> -p <phase>` | Capture audio/text for a phase |
| `sift phase transcribe <session> -p <phase>` | Transcribe audio |
| `sift phase extract <session> -p <phase>` | Extract structured data |
| `sift build generate <session>` | Generate all outputs |
| `sift build summary <session>` | Generate AI narrative summary |

### Templates
| Command | Description |
|---------|-------------|
| `sift template list` | List available templates |
| `sift template show <name>` | Show template details |
| `sift template init` | Create a new template interactively |

### Analysis
| Command | Description |
|---------|-------------|
| `sift analyze <path>` | Analyze project structure |
| `sift analyze <path> --template` | Generate template recommendation |
| `sift models` | List available AI models |

### Configuration
| Command | Description |
|---------|-------------|
| `sift config show` | Display resolved config |
| `sift config set <key> <value>` | Set config value |
| `sift config set-key <provider> <key>` | Store API key securely |
| `sift doctor show` | Environment diagnostics |
| `sift plugins` | List discovered plugins |

### Data Management
| Command | Description |
|---------|-------------|
| `sift export session <name>` | Export session as archive |
| `sift export template <name>` | Export template |
| `sift import-data session <file>` | Import session archive |
| `sift import-data template <file>` | Import template |
| `sift telemetry status` | Telemetry opt-in status |

### Global Flags
| Flag | Description |
|------|-------------|
| `--provider/-P <name>` | AI provider (anthropic, gemini, ollama) |
| `--model/-m <id>` | AI model override |
| `--plain` | Plain text output (no colors/panels) |
| `--json` | Machine-readable JSON output |
| `--verbose/-v` | Increase log verbosity |

## AI Providers

| Provider | Setup | Use Case |
|----------|-------|----------|
| **Anthropic** (Claude) | `sift config set-key anthropic KEY` | Best quality extraction |
| **Google Gemini** | `sift config set-key gemini KEY` | Alternative cloud provider |
| **Ollama** (local) | `ollama serve` | Offline, no API key needed |

```bash
# Switch providers
sift --provider ollama --model llama3.2 run my-session
sift config set providers.default ollama
```

## Input Methods

- **Upload audio:** `--file recording.mp3` (mp3, wav, webm, m4a, ogg, flac)
- **Upload transcript:** `--file transcript.txt` (txt, md)
- **Upload PDF:** `--file document.pdf` (auto-extracts text)
- **Type directly:** `--text` flag for inline entry
- **Interactive:** prompts you when no flags provided

## Installation

### From PyPI
```bash
pip install sift-cli[all]
```

### From source
```bash
git clone https://github.com/sirrele/sift.git
cd sift
pip install -e ".[all]"
```

### Optional dependency groups
```bash
pip install sift-cli[anthropic]   # Anthropic/Claude
pip install sift-cli[gemini]      # Google Gemini
pip install sift-cli[ollama]      # Ollama local AI
pip install sift-cli[tui]         # Textual interactive UI
pip install sift-cli[pdf]         # PDF extraction
pip install sift-cli[analyze]     # Tree-sitter code analysis
pip install sift-cli[mcp]         # MCP server
pip install sift-cli[all]         # Everything
```

### Docker
```bash
docker run -v $(pwd)/data:/data -e ANTHROPIC_API_KEY ghcr.io/sirrele/sift:latest ls
```

Or with docker-compose:
```bash
docker compose run sift new workflow-extraction --name my-session
```

## Agent Integration

### MCP Server (Claude Desktop / Claude Code)

```bash
# Claude Code
claude mcp add sift -- sift-mcp

# Claude Desktop - add to config:
# { "mcpServers": { "sift": { "command": "sift-mcp" } } }
```

### Plugin System

Third-party providers register via setuptools entry points:
```bash
pip install sift-openai  # Hypothetical third-party provider
sift plugins             # Shows all discovered plugins
```

## Creating Custom Templates

```bash
# Interactive template builder
sift template init

# Or write YAML directly
cat > templates/my-template.yaml << 'EOF'
name: "My Custom Session"
description: "What this template is for"

phases:
  - id: discovery
    name: "Discovery Phase"
    prompt: "Tell me about your situation."
    capture:
      - type: audio
        required: true
    extract:
      - id: pain_points
        type: list
        prompt: "Extract all pain points mentioned"
      - id: tools_used
        type: list
        prompt: "List all tools and systems mentioned"

outputs:
  - type: yaml
    template: session-config
  - type: markdown
    template: session-summary
EOF
```

## Included Templates

| Template | Phases | Use Case |
|----------|--------|----------|
| `workflow-extraction` | 4 | Map business workflows, identify gaps |
| `ghost-architecture` | 3 | Audit ad-hoc scripts and automations |
| `discovery-call` | 4 | Structure client discovery conversations |
| `last-mile-assessment` | 4 | Assess last-mile delivery decisions |

## Requirements

- Python 3.10+
- FFmpeg (optional, for audio processing)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and PR process.

## License

MIT - see [LICENSE](LICENSE)
