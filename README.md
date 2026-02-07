# sift

A domain-agnostic CLI for running structured sessions, capturing audio/transcripts, extracting structured data with AI, and generating configs.

**Use it for:** mentorship sessions, discovery calls, user interviews, workshops, or any conversation that needs structured outputs.

## Quick Start

```bash
# Install
pip install -e ".[all]"

# Enable AI features (transcription + extraction)
cp .env.example .env
# Edit .env and add your API key

# List available templates
sift template list

# Create a session
sift new workflow-extraction --name my-session

# Run interactively (guided walkthrough)
sift run my-session

# Or do it step by step:
sift phase capture my-session --phase describe --file recording.mp3
sift phase transcribe my-session --phase describe
sift phase extract my-session --phase describe
sift build generate my-session
```

## How It Works

### Templates
YAML files that define the structure of any session type. A mentorship role-play is one template. A discovery call is another.

```
templates/
  workflow-extraction.yaml
  discovery-call.yaml
  ghost-architecture.yaml
```

### Sessions
Each session is a directory with all captured data:

```
data/sessions/my-session/
  session.yaml          # State tracking
  template.yaml         # Copy of template used
  phases/
    describe/
      audio.mp3         # Raw recording
      transcript.txt    # Transcribed text
      extracted.yaml    # AI-extracted structured data
    reflect/
      ...
  outputs/
    session-config.yaml
    session-summary.md
```

### Phases
Each template has phases. Each phase can:
- **Capture** audio, transcript files, or direct text input
- **Transcribe** audio to text (via Claude API or local Whisper)
- **Extract** structured YAML data from transcripts using AI

### The Pipeline
```
Audio/Text → Transcribe → Extract → Build Outputs
```

## Commands

| Command | Description |
|---------|-------------|
| `sift new <template> --name <name>` | Create a session from a template |
| `sift run <session>` | Interactive guided walkthrough |
| `sift status <session>` | Show session progress |
| `sift ls` | List all sessions |
| `sift open <session>` | Interactive session workspace |
| `sift import <session> --file <pdf>` | Import multi-phase document |
| `sift template list` | List available templates |
| `sift template show <name>` | Show template details |
| `sift template init` | Create a new template interactively |
| `sift phase capture <session> -p <phase>` | Capture audio/text for a phase |
| `sift phase transcribe <session> -p <phase>` | Transcribe audio |
| `sift phase extract <session> -p <phase>` | Extract structured data |
| `sift build generate <session>` | Generate all outputs |
| `sift build summary <session>` | Generate AI narrative summary |
| `sift session export <session>` | Export everything as single YAML |
| `sift models` | List available AI models |

## Input Methods

- **Upload audio:** `--file recording.mp3` (supports mp3, wav, webm, m4a, ogg, flac)
- **Upload transcript:** `--file transcript.txt` (supports txt, md)
- **Upload PDF:** `--file document.pdf` (automatically extracts text)
- **Type directly:** `--text` flag for inline entry
- **Interactive:** prompts you to choose when no flags provided

## Installation

### From source (development)

```bash
git clone <repo-url>
cd sift
pip install -e ".[all]"
```

### Optional dependencies

```bash
pip install -e ".[anthropic]"  # Anthropic/Claude support
pip install -e ".[gemini]"     # Google Gemini support
pip install -e ".[pdf]"        # PDF extraction
pip install -e ".[all]"        # Everything
```

You can also run without installing:

```bash
python -m sift --help
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
      - id: desired_outcomes
        type: list
        prompt: "What outcomes does the speaker want?"

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
| `workflow-extraction` | 4 | Map business workflows, identify gaps, assess solutions |
| `ghost-architecture` | 3 | Audit ad-hoc scripts and automations |
| `discovery-call` | 4 | Structure client/stakeholder discovery conversations |
| `last-mile-assessment` | 4 | Assess last-mile delivery decisions |

## Requirements

- Python 3.10+
- FFmpeg (for audio processing, optional)
- AI provider API key for transcription + extraction:
  - `ANTHROPIC_API_KEY` for Claude
  - `GOOGLE_API_KEY` for Gemini

## Data Storage

**Default**: `./data/` (project-local, created automatically)

**Custom**: Set `SIFT_HOME` environment variable to store data elsewhere (e.g., `~/.sift/`, Dropbox, shared drive)

## License

MIT
