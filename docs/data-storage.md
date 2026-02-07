# Data Storage Strategy

## TL;DR

**By default, all your session data is stored in the project directory at `./data/`**

This keeps everything together and makes it easy to find your work!

---

## New Default: Project-Local Storage

### Structure
```
sift/
├── cli.py, cap, etc.         # Code
├── capture/                   # Source code
├── templates/                 # Template definitions (source)
│
└── data/                      # YOUR DATA (not in git)
    ├── templates/             # Installed templates
    └── sessions/              # Your sessions
        ├── my-session/
        ├── client-interview/
        └── workflow-docs/
```

### Why This Approach?

✅ **Everything in one place** - easy to find and understand
✅ **Easy to backup** - just copy the whole project directory
✅ **Works offline** - no dependencies on global paths
✅ **Project-specific** - different projects can have different sessions
✅ **Git-friendly** - `data/` is in `.gitignore`, so sessions aren't committed
✅ **Portable** - zip the directory and move it anywhere

---

## Three Storage Options

### Option 1: Project-Local (Default) ✨

**Location:** `./data/`

```bash
cd /path/to/sift
sift new workflow-extraction --name my-session
# Creates: ./data/sessions/my-session/
```

**Best for:**
- Single project usage
- Keeping everything together
- Easy discovery of files
- Beginners

**Backup strategy:**
```bash
# Backup entire project (code + data)
tar -czf sift-backup.tar.gz sift/

# Or just backup data
tar -czf sessions-backup.tar.gz sift/data/
```

---

### Option 2: Global Directory

**Location:** `~/.sift/`

Set the environment variable to use a global directory:

```bash
export SIFT_HOME=~/.sift
```

Add to shell profile to make permanent:
```bash
echo 'export SIFT_HOME=~/.sift' >> ~/.zshrc
```

**Best for:**
- Using sift from multiple project directories
- Centralized session management
- Sharing sessions across projects

**Backward compatibility:**
- If `~/.sift/` exists from previous setup, it will continue to be used automatically
- To migrate to project-local, simply run `setup.sh` again (it will create `./data/`)

---

### Option 3: Custom Location

**Location:** Anywhere you want!

```bash
# Store in Dropbox for sync
export SIFT_HOME=~/Dropbox/capture-sessions

# Store on external drive
export SIFT_HOME=/Volumes/External/capture-data

# Store in a team directory
export SIFT_HOME=/shared/team/capture-sessions
```

**Best for:**
- Cloud sync (Dropbox, iCloud, Google Drive)
- Team collaboration
- Backup to external drive
- Separating different environments (work/personal)

---

## Migration Guide

### From Global (~/.sift) to Project-Local (./data)

**Option A: Move the data**
```bash
cd /path/to/sift
mv ~/.sift/sessions ./data/sessions
mv ~/.sift/templates ./data/templates
```

**Option B: Keep both**
```bash
# Old sessions stay in ~/.sift
# New sessions go to ./data
# Both work fine!
```

**Option C: Symlink**
```bash
# Use global directory but access from project
cd /path/to/sift
ln -s ~/.sift data
```

---

## How It Works

The system checks for data location in this priority:

1. **`SIFT_HOME` environment variable** (if set)
   - Explicit override, always respected

2. **`./data/` directory** (project-local)
   - Default for new installations

3. **`~/.sift/` directory** (legacy global)
   - Backward compatibility
   - Used if it exists and `./data/` doesn't

### Example Scenarios

**Scenario 1: Fresh install**
```bash
bash setup.sh
# Creates: ./data/templates/ and ./data/sessions/
```

**Scenario 2: Existing ~/.sift/**
```bash
# You have ~/.sift/ from before
bash setup.sh
# Uses existing ~/.sift/ (backward compatible)
# To switch to project-local, set SIFT_HOME=
```

**Scenario 3: Custom location**
```bash
export SIFT_HOME=/custom/path
bash setup.sh
# Creates: /custom/path/templates/ and /custom/path/sessions/
```

---

## Checking Your Current Setup

```bash
# Show where data will be stored
python3 -c "from capture.config import Config; print(Config.get_capture_home())"

# Show in setup output
bash setup.sh
# Look for "Data Locations:" section
```

---

## Best Practices

### For Individual Use
- ✅ Use default project-local storage (`./data/`)
- ✅ Backup the entire project directory regularly
- ✅ Add `data/` to your `.gitignore` (already done)

### For Team Use
- ✅ Use custom `SIFT_HOME` pointing to shared network drive
- ✅ Version control the code, not the data
- ✅ Document where sessions are stored in team docs

### For Multiple Projects
**Option A: Separate per project (recommended)**
```bash
cd ~/projects/project-a/sift
sift new workflow-extraction --name proj-a-workflow
# Stored in ~/projects/project-a/sift/data/

cd ~/projects/project-b/sift
sift new discovery-call --name proj-b-discovery
# Stored in ~/projects/project-b/sift/data/
```

**Option B: Global shared data**
```bash
# In ~/.zshrc:
export SIFT_HOME=~/all-capture-sessions

# Now all projects share the same session pool
```

---

## Directory Comparison

### Before (Global Only)
```
/projects/sift/               # Code
~/.sift/                          # Data (separate location)
└── sessions/
```

**Issues:**
- Hard to find sessions
- Not obvious where data is stored
- Can't easily backup both together

### After (Project-Local Default)
```
/projects/sift/
├── capture/                         # Code
├── templates/                       # Template definitions
└── data/                            # Data (same location!)
    ├── templates/                   # Installed templates
    └── sessions/                    # Sessions
```

**Benefits:**
- Everything in one place
- Clear project structure
- Easy to understand and backup

---

## FAQ

**Q: Will my existing ~/.sift/ sessions still work?**
A: Yes! The system checks `~/.sift/` for backward compatibility.

**Q: Can I move between storage strategies?**
A: Yes, just copy your `sessions/` directory to the new location.

**Q: What if I want different strategies for different projects?**
A: Set `SIFT_HOME` in each project's `.env` file.

**Q: Is data/ in git?**
A: No, it's in `.gitignore` to prevent accidentally committing session data.

**Q: Can I store code and data in separate locations?**
A: Yes, use `SIFT_HOME` to point data elsewhere while code stays in the project.

**Q: What about cloud sync?**
A: Use `SIFT_HOME` to point to Dropbox/iCloud:
```bash
export SIFT_HOME=~/Dropbox/capture-sessions
```

---

## Visual Summary

```
┌─────────────────────────────────────────────────────────┐
│ SIFT_HOME Environment Variable                       │
│ (Optional - for custom location)                        │
└──────────────┬──────────────────────────────────────────┘
               │
               │ If not set...
               ↓
┌─────────────────────────────────────────────────────────┐
│ ./data/                                                  │
│ Project-local storage (NEW DEFAULT)                     │
│ ✓ Everything in one place                               │
│ ✓ Easy to find                                           │
│ ✓ Git-ignored                                            │
└──────────────┬──────────────────────────────────────────┘
               │
               │ If doesn't exist...
               ↓
┌─────────────────────────────────────────────────────────┐
│ ~/.sift/                                              │
│ Global directory (LEGACY FALLBACK)                      │
│ ✓ Backward compatible                                   │
└─────────────────────────────────────────────────────────┘
```

---

## Recommendation

**For most users:** Just use the default project-local storage (`./data/`). It's simple, self-contained, and easy to understand.

**For power users:** Use `SIFT_HOME` to customize exactly where you want data stored.
