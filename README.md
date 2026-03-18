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

### Connection Details

Set your Axigen server connection details as environment variables:

```bash
export AXIGEN_HOST=mail.example.com
export AXIGEN_PORT=7000
export AXIGEN_USER=admin
export AXIGEN_PASS=yourpassword
```

### SSL/TLS Connection

If your Axigen CLI service is configured to use SSL, enable it with:

```bash
export AXIGEN_SSL=true
```

By default, the script requires a valid SSL certificate from a trusted CA. For environments using self-signed or expired certificates, you can relax validation:

| Variable | Default | Description |
|----------|---------|-------------|
| `AXIGEN_SSL` | `false` | Set to `true` to connect via SSL/TLS |
| `AXIGEN_SSL_ALLOW_SELF_SIGNED` | `false` | Set to `true` to accept self-signed certificates |
| `AXIGEN_SSL_ALLOW_EXPIRED` | `false` | Set to `true` to accept expired certificates |

**Examples:**

```bash
# SSL with valid certificate (production)
export AXIGEN_SSL=true

# SSL with self-signed certificate (development/staging)
export AXIGEN_SSL=true
export AXIGEN_SSL_ALLOW_SELF_SIGNED=true

# SSL accepting both self-signed and expired (lab/testing only)
export AXIGEN_SSL=true
export AXIGEN_SSL_ALLOW_SELF_SIGNED=true
export AXIGEN_SSL_ALLOW_EXPIRED=true
```

SSL flags can also be passed as command-line arguments:

```bash
python3 axigen_cli.py --ssl --ssl-allow-self-signed "LIST Domains"
```

### Complete Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AXIGEN_HOST` | **Yes** | `127.0.0.1` | Server hostname or IP |
| `AXIGEN_PORT` | No | `7000` | CLI port |
| `AXIGEN_USER` | No | `admin` | Admin username |
| `AXIGEN_PASS` | **Yes** | — | Admin password |
| `AXIGEN_SSL` | No | `false` | Use SSL/TLS |
| `AXIGEN_SSL_ALLOW_SELF_SIGNED` | No | `false` | Accept self-signed certs |
| `AXIGEN_SSL_ALLOW_EXPIRED` | No | `false` | Accept expired certs |

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
- **axigen_cli.py** — Python CLI helper (plain telnet or SSL/TLS connection, authentication, command execution)
- **cli-reference.md** — Complete reference for all 126 CLI contexts and their commands

## Requirements

- Python 3.10+ (uses standard library `ssl` module — no extra dependencies)
- Network access to the Axigen server's CLI port (default: 7000)
- Admin credentials for the Axigen server

## License

MIT — see [LICENSE.md](https://github.com/axigen/plugin-cli-skill/blob/main/LICENSE.md)
