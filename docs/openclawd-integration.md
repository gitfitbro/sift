# OpenClawd Integration

Use SIFT as a conversational skill inside [OpenClawd](https://openclawd.ai), the open-source self-hosted AI assistant. This lets you run structured capture sessions from Slack, Discord, Telegram, or any messaging platform OpenClawd supports.

## Setup

### 1. Install SIFT on your OpenClawd machine

```bash
pip install sift-cli[all]
```

### 2. Configure an AI provider

```bash
sift config set-key anthropic YOUR_API_KEY
```

Or use a local provider (no API key needed):

```bash
# Ensure ollama is running on the same machine
sift config set providers.default ollama
```

### 3. Register SIFT as an OpenClawd skill

SIFT ships with a `skills.toml` that defines the skill metadata. The `SiftClawdSkill` class in `sift/integrations/openclaw.py` handles command dispatch.

To register with OpenClawd, add SIFT to your OpenClawd skill configuration:

```toml
# In your OpenClawd skills config
[skills.sift]
package = "sift-cli"
class = "sift.integrations.openclaw:SiftClawdSkill"
```

### 4. Verify

In any connected messaging channel:

```
/sift templates
```

You should see the list of available templates.

## Commands

| Command | Description |
|---------|-------------|
| `/sift templates` | List all available session templates |
| `/sift new <template> [name]` | Create a new session |
| `/sift capture <phase_id> <text>` | Capture text content for a phase |
| `/sift extract <phase_id>` | Extract structured data from a phase |
| `/sift next` | Show the next suggested action |
| `/sift status` | Show session progress |
| `/sift analyze <path>` | Analyze a project (captures to active session if one exists) |
| `/sift done` | Generate outputs and finish the session |
| `/sift help` | Show all commands |

## Example Workflows

### Discovery call in Slack

```
You: /sift new discovery-call client-acme

Sift: Session created: client-acme
      Template: Discovery Call
      Phases (4): context, goals, constraints, next_steps
      Next: capture content for 'context'

You: /sift capture context The client uses a microservices architecture
     with 12 AWS services. Main pain point is deployment takes 45 minutes.
     They want to reduce it to under 5 minutes.

Sift: Captured 182 chars for 'Current State'
      Status: transcribed

You: /sift extract context

Sift: Extracted 4 fields from 'Current State'
      Fields: current_tools, pain_points, desired_outcomes, success_metrics

You: /sift next

Sift: Session: client-acme (1/4 phases done)
      Next action: capture phase 'goals'
```

### Project analysis from Discord

```
You: /sift new infra-workflow-mapping my-infra-review

Sift: Session created: my-infra-review
      Template: Infrastructure Workflow Mapping
      Phases (4): infrastructure-inventory, dev-workflow, pain-points, improvement-roadmap
      Next: capture content for 'infrastructure-inventory'

You: /sift analyze /home/user/projects/my-api

Sift: Project: my-api
      Files: 247, Lines: 18,432
      Languages: Python (89), TypeScript (43), YAML (31)
      Frameworks: FastAPI, React
      Dependencies: 67

      Analysis captured to phase 'infrastructure-inventory' in session 'my-infra-review'

You: /sift extract infrastructure-inventory

Sift: Extracted 4 fields from 'Infrastructure Inventory'
      Fields: cloud_services, iac_tools, local_dev_tools, service_dependencies
```

### Using SIFT for multiple projects

SIFT tracks one active session per channel. You can run different sessions in different channels:

- **#chip-command** channel: `/sift new infra-workflow-mapping chip-review`
- **#trading-bot** channel: `/sift new workflow-extraction trading-pipeline`
- **#client-work** channel: `/sift new discovery-call client-xyz`

Each channel maintains its own session independently.

## Data Storage

Sessions are stored on the OpenClawd machine at `~/.sift/sessions/`. You can change the location:

```bash
# Set a custom data directory
export SIFT_HOME=/path/to/sift-data
```

All captured content, transcripts, extracted data, and generated outputs live in the session directory. Use `sift export session <name>` to export a session as a portable archive.

## Troubleshooting

**"No templates found"** -- Make sure SIFT is installed correctly. Run `sift template list` from the terminal to verify.

**"Error: API key not configured"** -- Run `sift config set-key anthropic YOUR_KEY` on the OpenClawd machine.

**Analysis not working** -- Ensure the project path is accessible from the OpenClawd machine. Use absolute paths.

**Session not found** -- Sessions are per-channel. Make sure you created the session in the same channel you are trying to use it from.
