# Axigen CLI Skill for Claude Code

A Claude Code skill that enables Claude to manage Axigen mail servers via the CLI admin interface. Claude can generate the exact CLI commands for any admin task or execute them directly on a live server.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3.6+ (standard library only, no pip installs)
- Network access to an Axigen server's CLI port (default: 7000)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/axigen/axigen-cli-claude-skill.git
   ```

2. Copy the skill to your Claude Code skills directory:
   ```bash
   cp -r axigen-cli-claude-skill/skills/axigen-cli ~/.claude/skills/
   ```

3. Set environment variables for live command execution:
   ```bash
   export AXIGEN_HOST=10.0.0.1        # Required: server IP/hostname
   export AXIGEN_PORT=7000             # Optional: CLI port (default: 7000)
   export AXIGEN_USER=admin            # Optional: admin username (default: admin)
   export AXIGEN_PASS=your_password    # Required: admin password
   ```

## Usage

Once installed, Claude will automatically use this skill when you ask about Axigen server administration. Examples:

- "Create a new domain example.com on Axigen"
- "Add user john to domain example.com with a 1GB quota"
- "List all accounts in example.com"
- "Stop the IMAP service"
- "Show me the SMTP outgoing configuration"
- "Check DNS MX records for example.com"

Claude can either generate the CLI commands for you to copy-paste, or execute them directly if the environment variables are configured.

## Skill Contents

| File | Purpose |
|------|---------|
| `SKILL.md` | Core skill: protocol docs, navigation model, safety rules, task recipes |
| `cli-reference.md` | Full CLI command reference (68 contexts, from Axigen 10.5.0) |
| `axigen_cli.py` | Python helper for executing commands on a live server |

## Refreshing the CLI Reference

The bundled reference is from Axigen 10.5.0. To update it for your server version:

1. Generate the help dump on your server:
   ```bash
   python3 ~/.claude/skills/axigen-cli/axigen_cli.py --dump-help /tmp/cliHelp.txt
   ```

2. Retrieve the file from the server:
   ```bash
   scp your-server:/tmp/cliHelp.txt .
   ```

3. Ask Claude to convert the dump and replace `cli-reference.md`.

## Standalone CLI Helper

The Python helper can also be used independently:

```bash
# Execute a sequence of commands
python3 axigen_cli.py --commands 'LIST Domains'

# Single query
python3 axigen_cli.py --query 'LIST Domains'

# Commands from stdin
echo 'LIST Domains' | python3 axigen_cli.py
```

## Related

- [Axigen Automation Tools](https://github.com/axigen/automation-tools) - Python scripts for common Axigen admin tasks
