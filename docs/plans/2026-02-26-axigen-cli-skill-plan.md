# Axigen CLI Claude Code Skill - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a distributable Claude Code skill that enables Claude to manage Axigen mail servers via CLI - both generating commands and executing them live.

**Architecture:** Monolithic skill package with three components: SKILL.md (protocol knowledge + recipes), cli-reference.md (full command reference converted from cliHelp dump), and axigen_cli.py (Python socket-based helper for live execution). Claude reads relevant reference sections on-demand and uses the helper to execute commands.

**Tech Stack:** Python 3.6+ (standard library only: socket, argparse, sys, os, re), Markdown, Claude Code skill format (YAML frontmatter)

**Design doc:** `docs/plans/2026-02-26-axigen-cli-skill-design.md`

---

### Task 1: Project Structure Setup

**Files:**
- Create: `skills/axigen-cli/` directory
- Verify: `cliHelp.10-5-0.txt` exists at project root (source material)

**Step 1: Create the skill directory structure**

```bash
mkdir -p skills/axigen-cli
```

**Step 2: Verify source material exists**

```bash
ls -la cliHelp.10-5-0.txt
```

Expected: File exists, ~157KB

**Step 3: Commit**

```bash
git init
git add docs/plans/
git commit -m "docs: add design doc and implementation plan for axigen-cli skill"
```

---

### Task 2: Python Helper Script - Core Connection

**Files:**
- Create: `skills/axigen-cli/axigen_cli.py`
- Create: `tests/test_axigen_cli.py`

**Step 1: Write failing test for socket connection and response parsing**

```python
#!/usr/bin/env python3
"""Tests for axigen_cli.py - uses mock sockets, no real server needed."""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'axigen-cli'))
from axigen_cli import AxigenCLI, parse_response

class TestParseResponse(unittest.TestCase):
    def test_parse_ok_response(self):
        code, message = parse_response("+OK: Authentication successful")
        self.assertTrue(code)
        self.assertEqual(message, "Authentication successful")

    def test_parse_err_response(self):
        code, message = parse_response("-ERR: Unknown command")
        self.assertFalse(code)
        self.assertEqual(message, "Unknown command")

    def test_parse_ok_no_message(self):
        code, message = parse_response("+OK")
        self.assertTrue(code)
        self.assertEqual(message, "")

class TestAxigenCLIAuth(unittest.TestCase):
    @patch('axigen_cli.socket.socket')
    def test_connect_and_auth(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        # Simulate: welcome banner, then user prompt, then password prompt, then auth OK
        mock_sock.recv.side_effect = [
            b"Welcome to AXIGEN's Command Line Interface\r\n"
            b"You must login first.\r\n<login> ",
            b"+OK\r\n<password> ",
            b"+OK: Authentication successful\r\n<#> ",
        ]

        cli = AxigenCLI('localhost', 7000, 'admin', 'secret')
        cli.connect()

        # Verify auth commands were sent
        calls = mock_sock.sendall.call_args_list
        self.assertIn(b'user admin\r\n', [c[0][0] for c in calls])
        self.assertIn(b'secret\r\n', [c[0][0] for c in calls])

class TestAxigenCLICommands(unittest.TestCase):
    @patch('axigen_cli.socket.socket')
    def test_send_command_ok(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            # Auth sequence
            b"Welcome\r\n<login> ",
            b"+OK\r\n<password> ",
            b"+OK: Authentication successful\r\n<#> ",
            # Command response
            b"domain1.com\r\ndomain2.com\r\n+OK\r\n<#> ",
        ]

        cli = AxigenCLI('localhost', 7000, 'admin', 'secret')
        cli.connect()
        success, output = cli.execute('LIST Domains')

        self.assertTrue(success)
        self.assertIn('domain1.com', output)

    @patch('axigen_cli.socket.socket')
    def test_send_command_err(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            b"Welcome\r\n<login> ",
            b"+OK\r\n<password> ",
            b"+OK: Authentication successful\r\n<#> ",
            b"-ERR: Unknown command\r\n<#> ",
        ]

        cli = AxigenCLI('localhost', 7000, 'admin', 'secret')
        cli.connect()
        success, output = cli.execute('INVALID COMMAND')

        self.assertFalse(success)

    @patch('axigen_cli.socket.socket')
    def test_disconnect_sends_quit(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            b"Welcome\r\n<login> ",
            b"+OK\r\n<password> ",
            b"+OK: Authentication successful\r\n<#> ",
            b"+OK\r\n",  # QUIT response
        ]

        cli = AxigenCLI('localhost', 7000, 'admin', 'secret')
        cli.connect()
        cli.disconnect()

        calls = [c[0][0] for c in mock_sock.sendall.call_args_list]
        self.assertIn(b'QUIT\r\n', calls)

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_axigen_cli.py -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'axigen_cli'`

**Step 3: Implement axigen_cli.py - core classes**

```python
#!/usr/bin/env python3
"""
Axigen CLI Helper - Execute commands on an Axigen mail server via CLI interface.

Usage:
    python3 axigen_cli.py --commands 'CMD1' 'CMD2' 'CMD3'
    python3 axigen_cli.py --query 'LIST Domains'
    python3 axigen_cli.py --dump-help /path/to/output.txt
    echo 'LIST Domains' | python3 axigen_cli.py

Environment variables:
    AXIGEN_HOST  - Server hostname/IP (required)
    AXIGEN_PORT  - CLI port (default: 7000)
    AXIGEN_USER  - Admin username (default: admin)
    AXIGEN_PASS  - Admin password (required)
"""

import socket
import argparse
import sys
import os
import re

CRLF = b'\r\n'
RECV_SIZE = 4096
DEFAULT_PORT = 7000
DEFAULT_USER = 'admin'
DEFAULT_TIMEOUT = 30

# Matches CLI prompts: <login>, <password>, <#>, <domain#>, <context#>, etc.
PROMPT_RE = re.compile(r'<[^>]*>\s*$')


def parse_response(line):
    """Parse a +OK/-ERR response line. Returns (success: bool, message: str)."""
    line = line.strip()
    if line.startswith('+OK'):
        msg = line[3:].lstrip(': ')
        return True, msg
    elif line.startswith('-ERR'):
        msg = line[4:].lstrip(': ')
        return False, msg
    return True, line


class AxigenCLI:
    """Socket-based client for the Axigen CLI interface."""

    def __init__(self, host, port, user, password, timeout=DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.timeout = timeout
        self.sock = None
        self.context = None

    def connect(self):
        """Connect to the server and authenticate."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.host, self.port))

        # Read welcome banner
        self._recv_until_prompt()

        # Authenticate
        self._send('user {}'.format(self.user))
        self._recv_until_prompt()

        self._send(self.password)
        data = self._recv_until_prompt()

        # Check auth succeeded
        if '+OK' not in data:
            raise ConnectionError('Authentication failed: {}'.format(data))

        self.context = '#'

    def execute(self, command):
        """Send a command and return (success: bool, output: str)."""
        self._send(command)
        data = self._recv_until_prompt()

        lines = data.strip().split('\n')
        output_lines = []
        success = True

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('+OK'):
                s, _ = parse_response(stripped)
                success = s
            elif stripped.startswith('-ERR'):
                s, msg = parse_response(stripped)
                success = False
                output_lines.append(stripped)
            elif stripped and not PROMPT_RE.match(stripped):
                output_lines.append(stripped)

        return success, '\n'.join(output_lines)

    def execute_sequence(self, commands, stop_on_error=True):
        """Execute a list of commands. Returns list of (command, success, output)."""
        results = []
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue
            success, output = self.execute(cmd)
            results.append((cmd, success, output))
            if not success and stop_on_error:
                break
        return results

    def disconnect(self):
        """Send QUIT and close the connection."""
        if self.sock:
            try:
                self._send('QUIT')
                self.sock.recv(RECV_SIZE)
            except (socket.error, OSError):
                pass
            finally:
                self.sock.close()
                self.sock = None

    def _send(self, data):
        """Send a line to the server."""
        self.sock.sendall(data.encode('utf-8') + CRLF)

    def _recv_until_prompt(self):
        """Read data until we see a CLI prompt pattern."""
        buf = b''
        while True:
            try:
                chunk = self.sock.recv(RECV_SIZE)
                if not chunk:
                    break
                buf += chunk
                text = buf.decode('utf-8', errors='replace')
                if PROMPT_RE.search(text):
                    # Extract context from prompt
                    m = re.search(r'<([^>]*)>\s*$', text)
                    if m:
                        self.context = m.group(1)
                    return text
            except socket.timeout:
                break
        return buf.decode('utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(
        description='Execute commands on an Axigen mail server via CLI'
    )
    parser.add_argument('--host', default=os.environ.get('AXIGEN_HOST'),
                        help='Server hostname/IP (or AXIGEN_HOST env var)')
    parser.add_argument('--port', type=int,
                        default=int(os.environ.get('AXIGEN_PORT', DEFAULT_PORT)),
                        help='CLI port (default: 7000)')
    parser.add_argument('--user', default=os.environ.get('AXIGEN_USER', DEFAULT_USER),
                        help='Admin username (default: admin)')
    parser.add_argument('--password', default=os.environ.get('AXIGEN_PASS'),
                        help='Admin password (or AXIGEN_PASS env var)')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT,
                        help='Timeout per command in seconds (default: 30)')
    parser.add_argument('--commands', nargs='+', metavar='CMD',
                        help='Commands to execute in sequence')
    parser.add_argument('--query', metavar='CMD',
                        help='Single read-only query command')
    parser.add_argument('--dump-help', metavar='PATH',
                        help='Generate CLI help from server and save to local path')

    args = parser.parse_args()

    if not args.host:
        print('Error: --host or AXIGEN_HOST env var required', file=sys.stderr)
        sys.exit(1)
    if not args.password:
        print('Error: --password or AXIGEN_PASS env var required', file=sys.stderr)
        sys.exit(1)

    cli = AxigenCLI(args.host, args.port, args.user, args.password, args.timeout)

    try:
        cli.connect()
        print('Connected to {}:{}'.format(args.host, args.port))

        if args.dump_help:
            # Generate CLI help on the server, then instruct user to retrieve it
            server_path = '/tmp/_axigen_cli_help_{}.txt'.format(os.getpid())
            results = cli.execute_sequence([
                'ENTER DEBUG',
                'EXEC listCliHelp {}'.format(server_path),
                'BACK',
            ])
            for cmd, success, output in results:
                print('> {}'.format(cmd))
                if output:
                    print(output)
                if not success:
                    print('Error during help dump', file=sys.stderr)
                    sys.exit(1)
            print('\nCLI help generated on server at: {}'.format(server_path))
            print('Retrieve it with: scp {}:{} {}'.format(
                args.host, server_path, args.dump_help))

        elif args.query:
            success, output = cli.execute(args.query)
            if output:
                print(output)
            sys.exit(0 if success else 1)

        elif args.commands:
            results = cli.execute_sequence(args.commands)
            exit_code = 0
            for cmd, success, output in results:
                print('> {}'.format(cmd))
                if output:
                    print(output)
                if success:
                    print('+OK')
                else:
                    print('-ERR')
                    exit_code = 1
                print()
            sys.exit(exit_code)

        else:
            # Read commands from stdin
            commands = [line.strip() for line in sys.stdin if line.strip()]
            if not commands:
                print('No commands provided. Use --commands, --query, or pipe via stdin.',
                      file=sys.stderr)
                sys.exit(1)
            results = cli.execute_sequence(commands)
            exit_code = 0
            for cmd, success, output in results:
                print('> {}'.format(cmd))
                if output:
                    print(output)
                if success:
                    print('+OK')
                else:
                    print('-ERR')
                    exit_code = 1
                print()
            sys.exit(exit_code)

    except ConnectionError as e:
        print('Connection error: {}'.format(e), file=sys.stderr)
        sys.exit(1)
    except socket.timeout:
        print('Connection timed out', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nInterrupted', file=sys.stderr)
    finally:
        cli.disconnect()


if __name__ == '__main__':
    main()
```

**Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_axigen_cli.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add skills/axigen-cli/axigen_cli.py tests/test_axigen_cli.py
git commit -m "feat: add axigen_cli.py helper with socket connection, auth, and command execution"
```

---

### Task 3: Convert cliHelp Dump to cli-reference.md

**Files:**
- Read: `cliHelp.10-5-0.txt` (source)
- Create: `skills/axigen-cli/cli-reference.md`

**Step 1: Write a conversion script**

Create a small Python script to convert the raw help dump to markdown. The script:
- Reads `cliHelp.10-5-0.txt`
- Replaces `Context: <name>` lines with `## Context: <name>` markdown headers
- Replaces `---` separator lines with nothing (headers are enough)
- Adds a document header with version info
- Preserves all command syntax exactly as-is

```python
#!/usr/bin/env python3
"""Convert Axigen cliHelp dump to markdown reference."""
import re
import sys

def convert(input_path, output_path, version='10.5.0'):
    with open(input_path, 'r') as f:
        lines = f.readlines()

    out = []
    out.append('# Axigen CLI Reference ({})\n'.format(version))
    out.append('')
    out.append('> Auto-generated from Axigen server cliHelp dump. Do not edit manually.')
    out.append('> To refresh, use: `python3 axigen_cli.py --dump-help` and reconvert.')
    out.append('')

    for line in lines:
        stripped = line.rstrip()
        # Skip separator lines
        if re.match(r'^-{10,}$', stripped):
            continue
        # Convert context headers
        m = re.match(r'^Context:\s+(.+)$', stripped)
        if m:
            out.append('## Context: {}'.format(m.group(1)))
            out.append('')
            continue
        # Convert "The commands available for..." to italic
        if stripped.startswith('The commands available for'):
            out.append('*{}*'.format(stripped))
            out.append('')
            continue
        # Preserve everything else
        out.append(stripped)

    with open(output_path, 'w') as f:
        f.write('\n'.join(out) + '\n')

if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '10.5.0')
```

**Step 2: Run the conversion**

```bash
python3 convert_help.py cliHelp.10-5-0.txt skills/axigen-cli/cli-reference.md 10.5.0
```

**Step 3: Verify the output looks correct**

```bash
head -30 skills/axigen-cli/cli-reference.md
grep -c "^## Context:" skills/axigen-cli/cli-reference.md
```

Expected: ~60 context headers, clean markdown formatting

**Step 4: Clean up the conversion script (it was a one-time tool)**

Delete `convert_help.py` - not needed in the package. The refresh workflow uses `--dump-help` and Claude does the conversion inline.

**Step 5: Commit**

```bash
git add skills/axigen-cli/cli-reference.md
git commit -m "feat: add full CLI reference converted from cliHelp 10.5.0 dump"
```

---

### Task 4: Write SKILL.md - Core Skill Document

**Files:**
- Create: `skills/axigen-cli/SKILL.md`
- Reference: `docs/plans/2026-02-26-axigen-cli-skill-design.md` (design doc)
- Reference: `skills/axigen-cli/cli-reference.md` (for context names)

**Step 1: Write SKILL.md**

The skill document must cover:

1. **Frontmatter** - name and description
2. **Overview** - what this skill enables
3. **Protocol** - telnet connection, auth, `+OK`/`-ERR`, context navigation
4. **Context navigation model** - hierarchical tree with COMMIT/BACK/DONE rules
5. **Generating commands** - rules Claude follows when producing CLI command sequences
6. **Executing commands** - how to use axigen_cli.py helper, env vars
7. **Reading the reference** - how to look up command syntax from cli-reference.md (read only relevant sections)
8. **Refreshing the reference** - on-demand dump from server
9. **Safety rules** - destructive command confirmation, password handling
10. **Common task recipes** - domain CRUD, account CRUD, service config, diagnostics, migration, backup

Write the full SKILL.md content following the design doc. Key points:
- Frontmatter `description` starts with "Use when..."
- Instruct Claude to read only the relevant `## Context:` section from cli-reference.md
- Include complete command sequences for each recipe (not pseudocode)
- Safety rules must be prominent and unambiguous

**Step 2: Verify the skill frontmatter is valid**

```bash
head -5 skills/axigen-cli/SKILL.md
```

Expected: Valid YAML frontmatter with `name: axigen-cli` and `description: Use when...`

**Step 3: Commit**

```bash
git add skills/axigen-cli/SKILL.md
git commit -m "feat: add core SKILL.md with protocol docs, recipes, and safety rules"
```

---

### Task 5: Write README.md - Installation & Setup Guide

**Files:**
- Modify: `README.md` (replace the current one-liner)

**Step 1: Write the README**

Cover:
- What this skill does (1-2 sentences)
- Prerequisites (Python 3.6+, Claude Code)
- Installation steps (clone, copy to `~/.claude/skills/` or configure in Claude Code)
- Environment variable setup (`AXIGEN_HOST`, `AXIGEN_PORT`, `AXIGEN_USER`, `AXIGEN_PASS`)
- Usage examples (asking Claude to create a domain, list accounts, etc.)
- Refreshing the CLI reference for a different Axigen version
- Link to the Axigen automation-tools repo for additional scripts

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add installation and setup guide"
```

---

### Task 6: Integration Verification

**Step 1: Verify the complete file structure**

```bash
find skills/ -type f | sort
```

Expected:
```
skills/axigen-cli/SKILL.md
skills/axigen-cli/axigen_cli.py
skills/axigen-cli/cli-reference.md
```

**Step 2: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: All tests PASS

**Step 3: Verify SKILL.md references are correct**

Check that every file path mentioned in SKILL.md actually exists:
- `cli-reference.md` - exists in same directory
- `axigen_cli.py` - exists in same directory

**Step 4: Verify the skill can be loaded**

Check frontmatter is valid YAML, description is under 1024 chars, name uses only letters/numbers/hyphens.

**Step 5: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "chore: integration verification fixes"
```

---

### Task 7: Final Review & Cleanup

**Step 1: Review all files for consistency**

- SKILL.md recipes match the actual cli-reference.md command syntax
- axigen_cli.py CLI interface matches what SKILL.md documents
- README.md installation steps are accurate
- No hardcoded paths or credentials anywhere

**Step 2: Remove source material from package**

The `cliHelp.10-5-0.txt` should stay in the repo root as reference material but is NOT part of the skill package in `skills/`.

**Step 3: Tag the release**

```bash
git tag v1.0.0
```
