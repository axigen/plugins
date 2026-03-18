# Axigen CLI Plugin for Claude Code

Manage Axigen mail servers directly from Claude Code.

## Installation

```bash
# Add the Axigen marketplace
/plugin marketplace add axigen/plugins

# Install the CLI skill
/plugin install axigen-cli
```

Or install directly from GitHub:

```bash
/plugin install axigen/plugin-cli-skill
```

## Setup

Set your Axigen server connection details:

```bash
export AXIGEN_HOST=mail.example.com
export AXIGEN_PORT=7000
export AXIGEN_USER=admin
export AXIGEN_PASS=yourpassword
```

## Usage

Once installed, just ask Claude to manage your Axigen server:

- "List all domains on the mail server"
- "Create a new domain called example.com"
- "Add an account john@example.com with password SecurePass123"
- "Check the mail queue for stuck messages"
- "Configure IMAP SSL with my certificate"
- "Show me the server license information"

Claude will use the `axigen_cli.py` helper to connect and execute the appropriate commands.

## What's Included

- **SKILL.md** — Skill definition with navigation model, common tasks, and context hierarchy
- **axigen_cli.py** — Python CLI helper (telnet connection, authentication, command execution)
- **cli-reference.md** — Complete reference for all 126 CLI contexts and their commands

## Requirements

- Python 3.10+
- Network access to the Axigen server's CLI port (default: 7000)
- Admin credentials for the Axigen server
