# Axigen CLI Plugin for Claude Code

Manage [Axigen](https://www.axigen.com) mail servers directly from Claude Code — through natural language.

> **For the latest documentation**, always refer to the **[skill README on GitHub](https://github.com/axigen/plugin-cli-skill)**.

## Installation

```bash
# Add the Axigen marketplace
/plugin marketplace add axigen/plugins

# Install the CLI skill
/plugin install axigen-cli

# Activate
/reload-plugins
```

Or install directly:

```bash
/plugin install axigen/plugin-cli-skill
```

## Two Ways to Use the Skill

### 1. Command Advisory Mode — "What commands should I run?"

For developers building automation (BSS/OSS provisioning, custom control panels, scripting). Claude generates the exact CLI command sequence — you integrate it into your systems. **No server connection needed.**

```
You: "What commands do I need to create a domain and add an account with a 5GB quota?"

Claude: Here's the complete sequence:
  <#> CREATE Domain name example.com domainLocation /axigen/var/domains/example.com ...
  <domain-create#> COMMIT
  <#> UPDATE Domain name example.com
  <domain#> ADD Account name john password <password>
  <domain-account#> CONFIG Quotas
  <domain-account-quotas#> SET totalMessageSize 5242880
  <domain-account-quotas#> DONE
  <domain-account#> COMMIT
  <#> SAVE CONFIG
```

### 2. Live Execution Mode — "Do this on my server"

For administrators who want hands-on help. Configure credentials, then Claude executes commands on your live server and shows you the results.

```
You: "Create a domain called company.com on my server"
Claude: [connects to server and executes, showing full transcript with prompts]
```

## CAUTION

> **AI-generated commands may contain errors.** The model may hallucinate commands, omit critical steps (COMMIT, SAVE CONFIG), or navigate to the wrong context. Destructive commands (REMOVE, PURGE, DELETE) can cause **permanent data loss**.
>
> **Always review commands before executing on production servers. Test on a staging environment first. Never grant unsupervised access to production mail servers.**

## Configuration

### Basic Connection

```bash
export AXIGEN_HOST=mail.example.com
export AXIGEN_PORT=7000
export AXIGEN_USER=admin
export AXIGEN_PASS=your-admin-password
```

### SSL/TLS Connection

If your Axigen CLI service uses SSL:

```bash
# Production — valid certificate from trusted CA
export AXIGEN_SSL=true

# Development/staging — self-signed certificate
export AXIGEN_SSL=true
export AXIGEN_SSL_ALLOW_SELF_SIGNED=true

# Lab/testing — self-signed and/or expired certificate
export AXIGEN_SSL=true
export AXIGEN_SSL_ALLOW_SELF_SIGNED=true
export AXIGEN_SSL_ALLOW_EXPIRED=true
```

SSL flags also work as command-line arguments:

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
| `AXIGEN_SSL` | No | `false` | Use SSL/TLS connection |
| `AXIGEN_SSL_ALLOW_SELF_SIGNED` | No | `false` | Accept self-signed certificates |
| `AXIGEN_SSL_ALLOW_EXPIRED` | No | `false` | Accept expired certificates |

### Security Notes

- **With SSL** (`AXIGEN_SSL=true`) — all traffic encrypted. Recommended for production.
- **Without SSL** — unencrypted telnet. Use on trusted networks or via SSH tunnel:
  ```bash
  ssh -L 7000:localhost:7000 user@mail.example.com
  export AXIGEN_HOST=127.0.0.1
  ```
- Avoid `AXIGEN_SSL_ALLOW_SELF_SIGNED` / `AXIGEN_SSL_ALLOW_EXPIRED` in production.
- Load passwords from a secrets manager in production:
  ```bash
  export AXIGEN_PASS=$(vault kv get -field=password secret/axigen/admin)
  ```

## Usage Examples

Once installed, ask Claude in natural language:

- "List all domains on the mail server"
- "Create a new domain called example.com"
- "Add an account john@example.com with password SecurePass123"
- "Suspend the account john@example.com"
- "What commands do I need to configure IMAP SSL?"
- "Check the mail queue for stuck messages"
- "Show me the server license information"

## What's Included

| File | Description |
|------|-------------|
| **SKILL.md** | Skill definition — CLI navigation model, common tasks, safety rules |
| **axigen_cli.py** | Python helper — plain telnet or SSL/TLS, authentication, command execution, transcript or JSON output |
| **cli-reference.md** | Complete reference for all 126 CLI contexts and their commands |

## Standalone Usage

`axigen_cli.py` also works without Claude Code:

```bash
# Plain telnet
python3 axigen_cli.py "LIST Domains"

# SSL
python3 axigen_cli.py --ssl "LIST Domains"

# SSL with self-signed cert
python3 axigen_cli.py --ssl --ssl-allow-self-signed "LIST Domains"

# JSON output for scripting
python3 axigen_cli.py --json "SHOW LicenseInfo"

# Multi-command workflow
python3 axigen_cli.py "UPDATE Domain name example.com" "LIST Accounts" "BACK"

# Commands from file
python3 axigen_cli.py --script provisioning-batch.txt

# Continue past errors
python3 axigen_cli.py --continue-on-error "CMD1" "CMD2" "CMD3"
```

## Requirements

- Python 3.10+ (uses standard library `ssl` module — no extra dependencies)
- Network access to the Axigen server's CLI port (default: 7000)
- Admin credentials for the Axigen server

## License

MIT — see [LICENSE.md](https://github.com/axigen/plugin-cli-skill/blob/main/LICENSE.md)
