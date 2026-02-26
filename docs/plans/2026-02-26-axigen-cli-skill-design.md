# Axigen CLI Claude Code Skill - Design Document

**Date:** 2026-02-26
**Status:** Approved

## Overview

A distributable Claude Code skill that enables Claude to manage Axigen mail servers via the CLI interface (telnet port 7000). The skill covers both command generation (Claude produces the exact CLI commands) and live execution (Claude runs commands on the server via a Python helper).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Use case | Generate commands + optionally execute | Covers both offline planning and live administration |
| Versioning | Bundled 10.5.0 default + on-demand refresh from server | Always works out of the box; can update via `ENTER DEBUG` → `EXEC listCliHelp` |
| Connection config | Environment variables | `AXIGEN_HOST`, `AXIGEN_PORT`, `AXIGEN_USER`, `AXIGEN_PASS` |
| Execution method | Bundled Python helper script | Socket-based, no external dependencies, similar to cli2.py from axigen/automation-tools |
| Reference scope | Full - all ~60 contexts | Complete coverage; Claude reads sections on-demand |
| Distribution | Distributable package | Any Claude Code user can install it |
| Approach | Monolithic skill (A) | Self-contained: SKILL.md + cli-reference.md + axigen_cli.py |

## File Structure

```
axigen-cli-claude-skill/
  README.md                          # Installation & setup guide
  skills/
    axigen-cli/
      SKILL.md                       # Core skill (~200 lines)
      cli-reference.md               # Full CLI reference by context (~2400 lines)
      axigen_cli.py                  # Python helper for live execution (~150 lines)
```

## Component Design

### SKILL.md - Core Skill

**Frontmatter:**
```yaml
---
name: axigen-cli
description: Use when the user needs to manage an Axigen mail server - creating domains, accounts, configuring services, running diagnostics, or any Axigen CLI administration task
---
```

**Contents:**
- Protocol overview (telnet, `+OK`/`-ERR` responses, context navigation)
- Command patterns (SET, ADD, UPDATE, REMOVE, CONFIG, COMMIT, BACK, DONE)
- Connection & authentication flow
- Context navigation model (hierarchical tree)
- How to generate commands for user requests
- How to execute commands (using the Python helper)
- How to refresh the CLI reference from a live server
- Common task recipes (domain CRUD, account CRUD, service config, diagnostics, migration, backup, bulk ops)
- Safety rules (destructive command confirmation, password handling)

**Key instruction:** Claude reads only the relevant `## Context: <name>` section from cli-reference.md based on the user's request, not the entire file.

### cli-reference.md - Full CLI Reference

Converted from `cliHelp.10-5-0.txt` into navigable markdown:
- One `## Context: <name>` section per CLI context
- Preserves exact command syntax from the help dump
- ~60 context sections covering all commands
- Header notes the Axigen version

### axigen_cli.py - Python Helper

**Interface:**
```bash
# Command sequence
python3 axigen_cli.py --commands 'CMD1' 'CMD2' 'CMD3'

# Commands from stdin
python3 axigen_cli.py < commands.txt

# Query mode (read-only)
python3 axigen_cli.py --query 'LIST Domains'

# Dump CLI help from server
python3 axigen_cli.py --dump-help /path/to/output.txt
```

**Environment variables:**
- `AXIGEN_HOST` (required)
- `AXIGEN_PORT` (default: 7000)
- `AXIGEN_USER` (default: admin)
- `AXIGEN_PASS` (required)

**Behavior:**
- Socket connection, sequential command execution
- Prints each command and its response
- Stops on `-ERR` (no partial commits)
- Exit code 0/1 for success/failure
- 30s timeout per command (configurable with `--timeout`)
- Python 3.6+ standard library only

## Protocol Model

**Context navigation:**
```
Root (<#>)
  ├── UPDATE Domain <name>        → domain context
  │     ├── UPDATE Account <name> → account context
  │     │     ├── CONFIG Quotas   → quotas subcontext
  │     │     │     └── DONE      → back to account
  │     │     └── COMMIT          → back to domain
  │     └── COMMIT                → back to root
  ├── CONFIG Server               → server context
  ├── CONFIG Imap                 → imap context
  └── etc.
```

**Key rules:**
1. Navigate to correct context before issuing commands
2. `COMMIT` saves changes and returns to parent context
3. `BACK` discards changes and returns to parent context
4. `DONE` (subcontexts like quotas/limits) saves and returns
5. `ADD` creates new objects (enters context for setup)
6. `UPDATE` enters existing objects for modification
7. `SAVE Config` at root persists all changes to disk

## Safety Model

**Require user confirmation before executing:**
- `REMOVE` (accounts, domains, listeners, etc.)
- `PURGE` (messages, metadata, backups)
- `STOP Service` on production services
- `COMPACT` storage
- `RESET` configurations
- `DEBUG` context commands

**Run freely (read-only):**
- `SHOW`, `LIST`, `HELP`, `QUERY`

**Password handling:**
- Placeholders `<password>` in generated commands
- `AXIGEN_PASS` env var for execution, never echoed
- Prompt user for account passwords

**Error recovery:**
- Stop on `-ERR`, no partial state (uncommitted changes discarded on disconnect)
- Always `QUIT` to close cleanly
- Timeouts prevent hanging

## Reference Refresh Workflow

1. Claude runs `python3 axigen_cli.py --dump-help`
2. Server generates help via `ENTER DEBUG` → `EXEC listCliHelp /tmp/_axigen_cli_help.txt`
3. User retrieves file from server (`scp` command provided by Claude)
4. Claude converts raw dump to markdown format
5. Claude overwrites `cli-reference.md` with new version
