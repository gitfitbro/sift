# sift

[![CI](https://github.com/sirrele/sift/actions/workflows/ci.yml/badge.svg)](https://github.com/sirrele/sift/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/sirrele/sift/pkgs/container/sift)

**Turn conversations into structured data.**

You have discovery calls, interviews, architecture reviews, workflow walkthroughs -- conversations that produce decisions, requirements, and context. But that knowledge gets trapped in recordings, notes, and memory. Next week you are starting over, re-explaining the same things.

SIFT gives you template-driven sessions that **capture** content, **extract** structured data with AI, and **generate** reusable outputs (YAML configs, markdown summaries, structured reports). The structured data persists across sessions and can feed into other tools.

```
Audio/Text/PDF  -->  Capture  -->  AI Extract  -->  Structured YAML + Markdown
```

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/sirrele/sift.git
cd sift
bash setup.sh
source .venv/bin/activate

# 2. Set up an AI provider (needed for extraction)
sift config set-key anthropic YOUR_API_KEY

# 3. See what templates are available
sift template list

# 4. Create and run a session
sift new discovery-call --name my-first-session
sift run my-first-session
```

The `run` command opens an interactive walkthrough. Each phase prompts you, captures your input (text, audio, or file), extracts structured data, and moves to the next phase. When all phases are done, it generates outputs.

## Templates

Templates define what a session captures and extracts. SIFT ships with these:

| Template | What it does | When to use it |
|----------|-------------|---------------|
| **discovery-call** | Captures client discovery conversations, extracts tools, pain points, desired outcomes | First call with a client or stakeholder |
| **workflow-extraction** | Maps a complete business workflow from a practitioner | Someone describes how their process works |
| **ghost-architecture** | Reverse-engineers undocumented system architecture | Auditing ad-hoc scripts, tribal knowledge |
| **last-mile-assessment** | Evaluates project readiness for launch | Before shipping, assessing what is left |
| **infra-workflow-mapping** | Maps infrastructure, dev tooling, and deployment pipelines | Engineering teams with IaC, sandboxes, CI/CD |

Each template has **phases** (structured steps) with **extraction rules** (what AI pulls out). You can combine templates: `sift new discovery-call+workflow-extraction`.

### Create your own

```bash
# Interactive builder
sift template init

# Or write YAML directly -- see templates/ directory for examples
```

## Three Ways to Use SIFT

### Path A: CLI

The standard way. Install, run commands, get outputs.

```bash
sift new workflow-extraction --name team-review
sift run team-review
# Follow the interactive prompts...
sift build generate team-review
```

### Path B: Agent / MCP (Claude Desktop or Claude Code)

SIFT runs as an MCP server, so Claude can create sessions, capture content, and extract data directly.

```bash
# Install with MCP support
pip install "sift-cli[mcp]"

# Register with Claude Code
claude mcp add sift -- sift-mcp

# Or Claude Desktop -- add to config:
# { "mcpServers": { "sift": { "command": "sift-mcp" } } }
```

Then in Claude: "Create a discovery call session and capture these notes..."

See [SKILL.md](SKILL.md) for the full MCP tool reference.

### Path C: OpenClawd (Slack, Discord, Telegram)

SIFT integrates with [OpenClawd](https://openclawd.ai) as a conversational skill for messaging platforms.

**1. Install SIFT on your OpenClawd machine:**

```bash
pip install sift-cli[all]
sift config set-key anthropic YOUR_API_KEY
```

**2. Register SIFT as an OpenClawd skill** by adding it to your OpenClawd skills config (usually `~/.openclawd/skills.toml` or your project's skill configuration):

```toml
[skills.sift]
package = "sift-cli"
class = "sift.integrations.openclaw:SiftClawdSkill"
```

**3. Verify** in any connected messaging channel:

```
/sift templates
```

You should see the list of available templates. Then use commands like `/sift new discovery-call`, `/sift capture context <your notes>`, `/sift extract context`.

See [docs/openclawd-integration.md](docs/openclawd-integration.md) for the full command reference and example workflows.

## Project Analysis

SIFT can analyze software projects and create sessions pre-populated with architecture data.

```bash
# Analyze a project
sift analyze /path/to/project

# Analyze and create a session in one step
sift analyze /path/to/project --session

# Generate a custom template recommendation
sift analyze /path/to/project --template --save

# Use an existing template with analysis data
sift new infra-workflow-mapping --analyze /path/to/project
```

## Commands Reference

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

### Analysis
| Command | Description |
|---------|-------------|
| `sift analyze <path>` | Analyze project structure |
| `sift analyze <path> --session` | Analyze and create a session |
| `sift analyze <path> --template --save` | Generate and save a template recommendation |

### Templates
| Command | Description |
|---------|-------------|
| `sift template list` | List available templates |
| `sift template show <name>` | Show template details |
| `sift template init` | Create a new template interactively |

### Configuration
| Command | Description |
|---------|-------------|
| `sift config show` | Display resolved config |
| `sift config set <key> <value>` | Set config value |
| `sift config set-key <provider> <key>` | Store API key securely |
| `sift doctor show` | Environment diagnostics |
| `sift plugins` | List discovered plugins |
| `sift models` | List available AI models |

### Data Management
| Command | Description |
|---------|-------------|
| `sift export session <name>` | Export session as archive |
| `sift export template <name>` | Export template |
| `sift import-data session <file>` | Import session archive |
| `sift import-data template <file>` | Import template |

### Global Flags
| Flag | Description |
|------|-------------|
| `--provider/-P <name>` | AI provider (anthropic, gemini, ollama) |
| `--model/-m <id>` | AI model override |
| `--plain` | Plain text output (no colors/panels) |
| `--json` | Machine-readable JSON output |
| `--verbose/-v` | Increase log verbosity |

## AI Providers

You need at least one provider configured for AI extraction to work.

| Provider | Setup | Best for |
|----------|-------|----------|
| **Anthropic** (Claude) | `sift config set-key anthropic KEY` | Best quality extraction |
| **Google Gemini** | `sift config set-key gemini KEY` | Alternative cloud provider |
| **Ollama** (local) | `ollama serve` | Offline use, no API key needed |

```bash
# Switch providers per-command
sift --provider ollama --model llama3.2 run my-session

# Or set a default
sift config set providers.default ollama
```

## Input Methods

- **Audio:** `--file recording.mp3` (mp3, wav, webm, m4a, ogg, flac)
- **Transcript:** `--file transcript.txt` (txt, md)
- **PDF:** `--file document.pdf` (auto-extracts text)
- **Text:** `--text` flag for inline entry
- **Interactive:** prompts you when no flags provided
- **Project analysis:** `--analyze /path` to analyze a codebase

## Installation

### From source (recommended)

```bash
git clone https://github.com/sirrele/sift.git
cd sift
bash setup.sh
source .venv/bin/activate
```

The setup script creates a virtual environment, installs all dependencies, and copies templates.

> **Debian/Ubuntu users:** If `setup.sh` fails with `ensurepip is not available`, install the venv package first:
> ```bash
> sudo apt install python3-venv
> # For a specific Python version, e.g.:
> # sudo apt install python3.12-venv
> ```
> Then re-run `bash setup.sh`.

### From PyPI

```bash
pip install sift-cli[all]
```

> **Note:** On modern Debian/Ubuntu (Python 3.12+), system pip is blocked by [PEP 668](https://peps.python.org/pep-0668/). Use a virtual environment instead:
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate
> pip install sift-cli[all]
> ```

### Optional dependency groups

Install only the providers and features you need:

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

## Plugin System

Third-party providers register via setuptools entry points:
```bash
pip install sift-openai  # Hypothetical third-party provider
sift plugins             # Shows all discovered plugins
```

## Requirements

- Python 3.10+
- FFmpeg (optional, for audio processing)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and PR process.

## License

MIT - see [LICENSE](LICENSE)
