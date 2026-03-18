# Axigen Plugins for Claude Code

Official plugin marketplace for [Axigen](https://www.axigen.com) mail server tools.

## How to Use

### 1. Add this marketplace

```
/plugin marketplace add axigen/plugins
```

### 2. Browse and install skills

```
/plugin install <skill-name>
/reload-plugins
```

## Available Skills

| Skill | Description | Repository |
|-------|-------------|------------|
| **axigen-cli** | Manage Axigen mail servers via CLI — create domains, accounts, configure services, manage queues, and more. Supports plain telnet and SSL/TLS connections. | [axigen/plugin-cli-skill](https://github.com/axigen/plugin-cli-skill) |

## Skill Details

### axigen-cli

AI-assisted Axigen mail server administration through Claude Code. Two modes:

- **Advisory mode** — ask Claude for CLI command sequences to integrate into your automation
- **Execution mode** — Claude connects to your server and runs commands live

**Quick start:**

```bash
# Install
/plugin marketplace add axigen/plugins
/plugin install axigen-cli
/reload-plugins

# Configure
export AXIGEN_HOST=mail.example.com
export AXIGEN_PASS=your-admin-password

# For SSL connections
export AXIGEN_SSL=true
```

**Full documentation, environment variables, SSL options, and usage examples:** see the [axigen-cli README](https://github.com/axigen/plugin-cli-skill).

## License

MIT
