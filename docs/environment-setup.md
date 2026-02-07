# Environment Variable Setup Guide

## Overview

sift uses environment variables for configuration. This guide shows you three ways to set them up.

## Required Variables

### `ANTHROPIC_API_KEY`
**Required for**: Transcription and AI extraction features
**Format**: `sk-ant-api03-...`
**Get yours**: https://console.anthropic.com/settings/keys

### `SIFT_HOME` (Optional)
**Purpose**: Change where session data is stored
**Default**: `~/.sift`
**Use when**: You want to store data in a custom location (e.g., Dropbox, external drive)

---

## Setup Method 1: Project .env File (Recommended)

**Best for**: Development, keeping keys out of shell history

### Steps:
```bash
# 1. Copy the example file
cd /path/to/sift
cp .env.example .env

# 2. Edit .env with your actual key
nano .env  # or use your preferred editor
```

**Your .env file should look like:**
```bash
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
# SIFT_HOME=/custom/path  # Uncomment to use custom location
```

**Pros:**
- ✅ Automatically loaded when you run `./cap`
- ✅ Not in shell history
- ✅ Easy to update
- ✅ Already in `.gitignore` (won't be committed)

**Cons:**
- ❌ Only works when running from project directory
- ❌ Need to recreate if you clone repo elsewhere

---

## Setup Method 2: Shell Profile (Persistent)

**Best for**: Using sift from anywhere, multiple projects

### For Zsh (macOS default):
```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-api03-...' >> ~/.zshrc
source ~/.zshrc
```

### For Bash:
```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-api03-...' >> ~/.bashrc
source ~/.bashrc
```

### Verify it worked:
```bash
echo $ANTHROPIC_API_KEY
```

**Pros:**
- ✅ Works from anywhere
- ✅ Persists across terminal sessions
- ✅ Available to all applications

**Cons:**
- ❌ Visible in shell history
- ❌ Applies system-wide (all projects use same key)

---

## Setup Method 3: Session Export (Temporary)

**Best for**: Testing, one-time usage

### Set for current terminal session only:
```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
export SIFT_HOME=/tmp/test-sessions  # optional
```

**Pros:**
- ✅ Quick and easy
- ✅ No permanent changes

**Cons:**
- ❌ Lost when you close the terminal
- ❌ Need to re-export every time

---

## Verification

### Check if API key is set:
```bash
# Method 1: Check environment variable
echo $ANTHROPIC_API_KEY

# Method 2: Try a CLI command that needs it
sift phase transcribe --help  # Won't fail, just shows help
```

### Check which SIFT_HOME is being used:
```bash
# The CLI will show this in setup output
bash setup.sh

# Or check manually:
echo ${SIFT_HOME:-~/.sift}
```

---

## Troubleshooting

### "ANTHROPIC_API_KEY not set" error

**Symptom:**
```
ValueError: ANTHROPIC_API_KEY not set. Set it with:
  export ANTHROPIC_API_KEY=sk-ant-api03-...
```

**Solutions:**

1. **If using .env file**, make sure:
   - File is named exactly `.env` (not `env` or `.env.txt`)
   - File is in the sift project directory
   - You're running `./cap` from the project directory
   - Key is not quoted: `ANTHROPIC_API_KEY=sk-ant-...` (NOT `"sk-ant-..."`)

2. **If using shell profile**, verify:
   ```bash
   echo $ANTHROPIC_API_KEY  # Should show your key
   ```

   If empty, check:
   - Did you reload shell? (`source ~/.zshrc` or open new terminal)
   - Is it in the right file? (`.zshrc` for zsh, `.bashrc` for bash)
   - Did you use `export`? (Just `ANTHROPIC_API_KEY=...` won't work)

3. **If using export**, make sure:
   - You ran it in the same terminal session
   - No typos in the variable name (case-sensitive!)

---

## Security Best Practices

### ✅ DO:
- Use `.env` file for development
- Add `.env` to `.gitignore` (already done)
- Rotate keys if accidentally committed
- Use different keys for different projects/environments

### ❌ DON'T:
- Commit `.env` to git
- Share keys in chat/email
- Use production keys for testing
- Hardcode keys in Python files

---

## Custom Data Location

### Why use a custom SIFT_HOME?

1. **Sync across devices**: Store in Dropbox/iCloud
2. **Backup**: Store on external drive
3. **Team sharing**: Store on network drive
4. **Separation**: Keep work/personal sessions separate

### Example: Store in Dropbox
```bash
# In .env file:
SIFT_HOME=~/Dropbox/capture-sessions

# Or in shell profile:
export SIFT_HOME=~/Dropbox/capture-sessions
```

### Example: Multiple environments
```bash
# Work sessions
export SIFT_HOME=~/work/capture-sessions
sift new discovery-call --name client-x

# Personal sessions
export SIFT_HOME=~/personal/capture-sessions
sift new workflow-extraction --name my-project
```

---

## Advanced: Environment-Specific Keys

### Use different API keys for different purposes:

**In .env:**
```bash
# Production key (rate-limited, tracked)
ANTHROPIC_API_KEY=sk-ant-api03-production-key

# Development key (for testing)
# ANTHROPIC_API_KEY=sk-ant-api03-dev-key
```

Comment/uncomment as needed, or use different .env files:

```bash
# Load production env
sift --env .env.prod run my-session

# Load development env
sift --env .env.dev run test-session
```

*(Note: Multiple .env support would need to be implemented)*

---

## Quick Reference

| Method | Persistence | Scope | Best For |
|--------|-------------|-------|----------|
| `.env` file | Project | Project only | Development, secrets |
| Shell profile | Permanent | System-wide | Daily usage |
| `export` | Session | Current terminal | Testing |

---

## Testing Your Setup

### Full environment check:
```bash
# 1. Check Python dependencies
python3 -c "import typer, rich, yaml, jinja2, anthropic, dotenv; print('✓ Dependencies OK')"

# 2. Check API key (without revealing it)
python3 -c "from capture.config import Config; print('✓ API key set' if Config.get_anthropic_api_key() else '✗ API key missing')"

# 3. Check SIFT_HOME
python3 -c "from capture.config import Config; print(f'✓ SIFT_HOME: {Config.get_capture_home()}')"

# 4. Run a CLI command
sift template list
```

If all these work, you're ready to go! 🎉
