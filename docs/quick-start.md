# Quick Start Guide

## First Time Setup (5 minutes)

### 1. Install
```bash
cd /path/to/sift
bash setup.sh
```

This will:
- ✅ Check Python version (3.10+ required)
- ✅ Install dependencies (typer, rich, pyyaml, etc.)
- ✅ Create `~/.sift/` directory
- ✅ Copy templates to `~/.sift/templates/`

### 2. Set API Key (for AI features)
```bash
export ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

Add to your `~/.zshrc` or `~/.bashrc` to make it permanent:
```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-api03-...' >> ~/.zshrc
```

### 3. Test It Works
```bash
sift template list
```

You should see a table of available templates.

---

## Your First Session (10 minutes)

### Step 1: Create a Session
```bash
sift new workflow-extraction --name my-first-session
```

This creates: `~/.sift/sessions/my-first-session/`

### Step 2: Run Interactive Mode
```bash
sift run my-first-session
```

The interactive mode will guide you through:
1. **Describe** phase: Upload audio or type text about the workflow
2. **Reflect** phase: Validate and add missing details
3. **Assess** phase: Evaluate solution options
4. **Org Context** phase: Capture organizational constraints

Or do it manually:

### Step 3: Capture Phase Data
```bash
# Option A: Upload an audio file
sift phase capture my-first-session -p describe --file recording.mp3

# Option B: Upload a transcript
sift phase capture my-first-session -p describe --file transcript.txt

# Option C: Type it directly
sift phase capture my-first-session -p describe --text
```

### Step 4: Transcribe (if you uploaded audio)
```bash
sift phase transcribe my-first-session -p describe
```

This sends audio to Claude API for transcription.

### Step 5: Extract Structured Data
```bash
sift phase extract my-first-session -p describe
```

AI extracts structured YAML based on template extraction rules.

### Step 6: Repeat for Other Phases
```bash
sift phase capture my-first-session -p reflect --text
sift phase transcribe my-first-session -p reflect  # if audio
sift phase extract my-first-session -p reflect
# ... continue for 'assess' and 'org_context'
```

### Step 7: Generate Final Outputs
```bash
sift build generate my-first-session
```

This creates:
- `~/.sift/sessions/my-first-session/outputs/session-config.yaml`
- `~/.sift/sessions/my-first-session/outputs/session-summary.md`

### Step 8: View Results
```bash
cat ~/.sift/sessions/my-first-session/outputs/session-summary.md
```

---

## Understanding the File Structure

```
/projects/sift/          ← Source code (this is where you run sift from)
├── cli.py
├── cap
├── capture/
└── templates/

~/.sift/                     ← Your data (sessions, outputs)
├── templates/                  ← Installed templates
│   └── workflow-extraction.yaml
└── sessions/                   ← All your sessions
    └── my-first-session/       ← One session
        ├── session.yaml        ← Progress tracking
        ├── template.yaml       ← Copy of template used
        ├── phases/             ← Data from each phase
        │   ├── describe/
        │   │   ├── audio.mp3
        │   │   ├── transcript.txt
        │   │   └── extracted.yaml
        │   ├── reflect/
        │   ├── assess/
        │   └── org_context/
        └── outputs/            ← Generated files
            ├── session-config.yaml
            └── session-summary.md
```

**Key Concept**:
- **Project directory** = code (version controlled)
- **~/.sift/** = your data (not in git)

---

## Common Commands

```bash
# List all sessions
sift ls

# Check session progress
sift status my-session

# List available templates
sift template list

# Show template details
sift template show workflow-extraction

# Create a custom template
sift template init

# Export everything as one YAML file
sift session export my-session
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'typer'"

**Solution:**
```bash
cd /projects/sift
pip3 install -r requirements.txt
```

**Why:** Dependencies aren't installed for your current Python version.

### "Session not found"

**Check:**
```bash
ls ~/.sift/sessions/
```

Make sure you're using the exact session name.

### "API key not set"

**Solution:**
```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

Or add it permanently to `~/.zshrc` or `~/.bashrc`.

---

## Next Steps

- Read [architecture.md](architecture.md) for detailed documentation
- Create custom templates with `sift template init`
- Try other templates: `discovery-call`, `ghost-architecture`
- Build your own templates by editing YAML files

---

## Tips

1. **Use interactive mode** (`sift run`) for first-time sessions - it guides you through everything
2. **Audio files** should be mp3, wav, webm, m4a, ogg, or flac
3. **Transcripts** can be txt or md files
4. **Sessions are self-contained** - you can back up just `~/.sift/sessions/` to save all your work
5. **Templates are versioned** - each session includes a copy of the template used
