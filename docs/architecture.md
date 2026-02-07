# sift Architecture

## Directory Structure

### Project Source (`/projects/sift/`)
The codebase lives here - this is where you develop and run the CLI from.

```
/projects/sift/
├── cli.py                 # Main CLI entry point
├── cap                    # Launcher script (calls cli.py)
├── setup.sh               # Installation script
├── requirements.txt       # Python dependencies
├── capture/               # Core application code
│   ├── models.py         # Data models (Template, Session, Phase)
│   ├── engine.py         # Core processing logic
│   ├── interactive.py    # Interactive mode
│   └── commands/         # CLI command implementations
│       ├── template_cmd.py
│       ├── session_cmd.py
│       ├── phase_cmd.py
│       └── build_cmd.py
└── templates/            # Default template definitions
    ├── workflow-extraction.yaml
    ├── discovery-call.yaml
    └── ghost-architecture.yaml
```

### User Data Directory (`~/.sift/`)
All your sessions, recordings, and generated outputs are stored here.

```
~/.sift/
├── templates/            # Installed templates (copied from project)
│   ├── workflow-extraction.yaml
│   ├── discovery-call.yaml
│   └── ghost-architecture.yaml
│
└── sessions/            # All your session data
    └── my-session/      # One session directory
        ├── session.yaml          # Session state & progress tracking
        ├── template.yaml         # Copy of template used for this session
        ├── phases/              # Data for each phase
        │   ├── describe/
        │   │   ├── audio.mp3           # Original recording
        │   │   ├── transcript.txt      # AI-transcribed text
        │   │   └── extracted.yaml      # Structured data extracted by AI
        │   ├── reflect/
        │   ├── assess/
        │   └── org_context/
        └── outputs/             # Final generated outputs
            ├── session-config.yaml     # Structured configuration
            └── session-summary.md      # AI-generated summary
```

## Data Flow

```
1. CREATE SESSION
   sift new workflow-extraction --name my-session
   → Creates ~/.sift/sessions/my-session/
   → Copies template to session directory
   → Initializes session.yaml with phase states

2. CAPTURE PHASE DATA
   sift phase capture my-session -p describe --file recording.mp3
   → Saves audio to ~/.sift/sessions/my-session/phases/describe/audio.mp3
   → Updates session.yaml (status: captured, audio_file: audio.mp3)

3. TRANSCRIBE AUDIO
   sift phase transcribe my-session -p describe
   → Reads audio from phases/describe/audio.mp3
   → Calls Anthropic API to transcribe
   → Saves to phases/describe/transcript.txt
   → Updates session.yaml (status: transcribed, transcript_file: transcript.txt)

4. EXTRACT STRUCTURED DATA
   sift phase extract my-session -p describe
   → Reads phases/describe/transcript.txt
   → Uses AI with extraction prompts from template
   → Saves to phases/describe/extracted.yaml
   → Updates session.yaml (status: extracted, extracted_file: extracted.yaml)

5. GENERATE OUTPUTS
   sift build generate my-session
   → Reads all extracted.yaml files from all phases
   → Uses Jinja2 templates to generate outputs
   → Saves to outputs/ directory
```

## Key Concepts

### Templates (YAML Definitions)
- Define the structure of a session type
- Specify phases, prompts, and what to extract
- Located in `~/.sift/templates/`
- Versioned and shareable

### Sessions (Active Workspaces)
- One directory per session in `~/.sift/sessions/`
- Contains all captured data, transcripts, and outputs
- Self-contained (includes copy of template used)
- Session state tracked in `session.yaml`

### Phases (Stages of Data Collection)
- Each phase can capture audio/text
- Each phase gets transcribed
- Each phase has extraction rules
- Phases can depend on previous phases

### Extraction (AI-Powered Structuring)
- Uses Claude API to extract structured data from transcripts
- Each extraction field has:
  - `id`: Field name in output YAML
  - `type`: list, map, text, or boolean
  - `prompt`: Instructions for AI extraction

## Environment Variables

```bash
# Required for AI features (transcription + extraction)
export ANTHROPIC_API_KEY=sk-ant-api03-...

# Optional: Change where data is stored (default: ~/.sift)
export SIFT_HOME=/path/to/custom/location
```

## Python Environment Setup

The CLI requires Python 3.10+ and several dependencies:
- `typer`: CLI framework
- `rich`: Terminal formatting
- `pyyaml`: YAML parsing
- `jinja2`: Template rendering
- `anthropic`: Claude API client
- `pydub`: Audio processing

### Installation Methods

**Method 1: Run setup.sh (Recommended)**
```bash
bash setup.sh
```

**Method 2: Manual pip install**
```bash
pip3 install -r requirements.txt
```

**Method 3: Direct install**
```bash
pip3 install typer rich pyyaml jinja2 anthropic pydub
```

### Common Issues

**Issue: `ModuleNotFoundError: No module named 'typer'`**
- **Cause**: Dependencies not installed for the Python version being used
- **Solution**: Run `pip3 install -r requirements.txt` from the project directory
- **Why it happens**: If using pyenv or multiple Python versions, packages must be installed for the active Python version

**Issue: `setup.sh` ran but dependencies still missing**
- **Cause**: `setup.sh` uses `pip` which may install to a different Python than `python3`
- **Solution**: Use `pip3` directly or ensure `pip` and `python3` point to the same Python
- **Check**: Run `which python3` and `which pip3` to verify they match

## File Permissions

The `cap` launcher script must be executable:
```bash
chmod +x /projects/sift/cap
```

## Testing the Installation

```bash
# Verify dependencies are installed
python3 -c "import typer, rich, yaml, jinja2, anthropic, pydub; print('✓ All dependencies installed')"

# List available templates
sift template list

# Check help
sift --help
```

## Session Lifecycle Example

```bash
# 1. Create session
sift new discovery-call --name client-interview-2024

# 2. Interactive mode (guides you through all phases)
sift run client-interview-2024

# Or do it step-by-step:
# 3. Capture first phase
sift phase capture client-interview-2024 -p context --file recording.mp3

# 4. Transcribe
sift phase transcribe client-interview-2024 -p context

# 5. Extract structured data
sift phase extract client-interview-2024 -p context

# 6. Repeat for remaining phases...

# 7. Generate final outputs
sift build generate client-interview-2024

# 8. View results
cat ~/.sift/sessions/client-interview-2024/outputs/session-summary.md
```

## Why Two Directories?

**Project Directory** (`/projects/sift/`)
- Source code you can modify
- Development environment
- Version controlled with git
- Contains the CLI tool itself

**Data Directory** (`~/.sift/`)
- Your actual work (sessions, recordings, outputs)
- Not version controlled
- Persists independently of code updates
- Can be backed up separately

This separation follows Unix conventions and allows you to:
- Update the CLI without affecting your data
- Store data in a different location (via `SIFT_HOME`)
- Back up your sessions independently
- Share templates without sharing session data
