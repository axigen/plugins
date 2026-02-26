#!/usr/bin/env python3
"""Axigen CLI helper - socket-based admin interface for Axigen mail servers.

Connects to the Axigen CLI (telnet port 7000) and executes commands.
Designed for use by Claude Code skill to manage Axigen servers.

Usage:
    # Execute a sequence of commands
    python3 axigen_cli.py --host mail.example.com --password secret --commands 'LIST Domains' 'SHOW'

    # Single read-only query
    python3 axigen_cli.py --query 'LIST Domains'

    # Read commands from stdin
    echo 'LIST Domains' | python3 axigen_cli.py --host mail.example.com --password secret

    # Dump CLI help from server
    python3 axigen_cli.py --dump-help /tmp/cliHelp.txt

Environment variables:
    AXIGEN_HOST  - Server hostname (required if --host not given)
    AXIGEN_PORT  - Server port (default: 7000)
    AXIGEN_USER  - Admin username (default: admin)
    AXIGEN_PASS  - Admin password (required if --password not given)
"""

import argparse
import os
import re
import socket
import sys

# Prompt pattern: matches <login> , <#> , <domain#> , <account-quotas#> , etc.
PROMPT_RE = re.compile(r'<[^>]*>\s*$')


def parse_response(line):
    """Parse a +OK/-ERR response line from Axigen CLI.

    Args:
        line: Response line from the server.

    Returns:
        Tuple of (success: bool, message: str).
        success is True for +OK, False for -ERR or unrecognized lines.
    """
    line = line.strip()

    if line.startswith('+OK'):
        # Extract message after "+OK" - may have ": message" or just "+OK"
        if ':' in line:
            message = line.split(':', 1)[1].strip()
        else:
            message = line[3:].strip()
        return (True, message)

    if line.startswith('-ERR'):
        if ':' in line:
            message = line.split(':', 1)[1].strip()
        else:
            message = line[4:].strip()
        return (False, message)

    # Unrecognized line
    return (False, line)


class AxigenCLI:
    """Client for the Axigen CLI admin interface.

    Connects via TCP socket, authenticates, and executes commands
    using the Axigen text protocol.
    """

    def __init__(self, host, port, user, password, timeout=30):
        """Initialize the CLI client.

        Args:
            host: Axigen server hostname or IP.
            port: CLI port (typically 7000).
            user: Admin username.
            password: Admin password.
            timeout: Socket timeout in seconds.
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.timeout = timeout
        self._sock = None

    def connect(self):
        """Connect to the Axigen CLI and authenticate.

        Raises:
            ConnectionError: If connection fails.
            Exception: If authentication fails.
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect((self.host, self.port))

        # Read the welcome banner (ends with <login> prompt)
        self._recv_until_prompt()

        # Send username
        self._send("user {}".format(self.user))
        self._recv_until_prompt()

        # Send password
        self._send(self.password)
        response = self._recv_until_prompt()

        # Check if authentication was successful
        for line in response.splitlines():
            line = line.strip()
            if line.startswith('-ERR'):
                self._sock.close()
                self._sock = None
                _, msg = parse_response(line)
                raise Exception("Authentication failed: {}".format(msg))

    def execute(self, command):
        """Execute a single command and return the result.

        Args:
            command: The CLI command to execute.

        Returns:
            Tuple of (success: bool, output: str).
        """
        self._send(command)
        response = self._recv_until_prompt()

        # Parse the response to determine success/failure
        success = True
        for line in response.splitlines():
            line = line.strip()
            if line.startswith('-ERR'):
                success = False
                break
            if line.startswith('+OK'):
                success = True
                break

        return (success, response.strip())

    def execute_sequence(self, commands, stop_on_error=True):
        """Execute a sequence of commands.

        Args:
            commands: List of command strings to execute.
            stop_on_error: If True, stop on first -ERR response.

        Returns:
            List of (command, success, output) tuples for each executed command.
        """
        results = []
        for cmd in commands:
            success, output = self.execute(cmd)
            results.append((cmd, success, output))
            if not success and stop_on_error:
                break
        return results

    def disconnect(self):
        """Send QUIT and close the connection."""
        if self._sock is None:
            return

        try:
            self._send("QUIT")
            # Try to read any farewell message, but don't require it
            try:
                self._sock.recv(4096)
            except (socket.timeout, OSError):
                pass
        except (socket.timeout, OSError):
            pass
        finally:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _send(self, data):
        """Send a line to the server with CRLF termination.

        Args:
            data: The string to send (without line ending).
        """
        self._sock.sendall((data + "\r\n").encode('utf-8'))

    def _recv_until_prompt(self):
        """Read data from the socket until a CLI prompt is detected.

        Prompts match the pattern <...> followed by optional whitespace
        at the end of the received data (e.g., '<login> ', '<#> ', '<domain#> ').

        Returns:
            The accumulated response data as a string.

        Raises:
            socket.timeout: If no prompt is received within the timeout period.
            ConnectionError: If the connection is closed unexpectedly.
        """
        buf = b''
        while True:
            chunk = self._sock.recv(4096)
            if not chunk:
                # Connection closed
                break
            buf += chunk
            # Check if we have a complete prompt
            text = buf.decode('utf-8', errors='replace')
            if PROMPT_RE.search(text):
                return text
        return buf.decode('utf-8', errors='replace')


def main():
    """Main entry point with argparse CLI.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    parser = argparse.ArgumentParser(
        description='Axigen CLI helper - execute commands on Axigen mail servers'
    )
    parser.add_argument(
        '--host',
        default=os.environ.get('AXIGEN_HOST'),
        help='Axigen server hostname (or AXIGEN_HOST env var)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.environ.get('AXIGEN_PORT', '7000')),
        help='Axigen CLI port (or AXIGEN_PORT env var, default: 7000)'
    )
    parser.add_argument(
        '--user',
        default=os.environ.get('AXIGEN_USER', 'admin'),
        help='Admin username (or AXIGEN_USER env var, default: admin)'
    )
    parser.add_argument(
        '--password',
        default=os.environ.get('AXIGEN_PASS'),
        help='Admin password (or AXIGEN_PASS env var)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Socket timeout in seconds (default: 30)'
    )
    parser.add_argument(
        '--commands',
        nargs='+',
        metavar='CMD',
        help='Commands to execute in sequence'
    )
    parser.add_argument(
        '--query',
        metavar='CMD',
        help='Single read-only query to execute'
    )
    parser.add_argument(
        '--dump-help',
        metavar='PATH',
        help='Generate CLI help dump on server at the given path'
    )

    args = parser.parse_args()

    # Validate required arguments
    if not args.host:
        parser.error('--host is required (or set AXIGEN_HOST env var)')
    if not args.password:
        parser.error('--password is required (or set AXIGEN_PASS env var)')

    cli = AxigenCLI(args.host, args.port, args.user, args.password, args.timeout)

    try:
        cli.connect()

        if args.commands:
            return _run_commands_mode(cli, args.commands)
        elif args.query:
            return _run_query_mode(cli, args.query)
        elif args.dump_help:
            return _run_dump_help_mode(cli, args.dump_help)
        else:
            return _run_stdin_mode(cli)

    except Exception as e:
        print("ERROR: {}".format(e), file=sys.stderr)
        return 1
    finally:
        cli.disconnect()


def _run_commands_mode(cli, commands):
    """Execute a sequence of commands and print results.

    Returns:
        Exit code: 0 if all succeeded, 1 if any failed.
    """
    results = cli.execute_sequence(commands, stop_on_error=True)
    exit_code = 0

    for cmd, success, output in results:
        status = "OK" if success else "ERR"
        print(">>> {}".format(cmd))
        print("[{}] {}".format(status, output))
        print()
        if not success:
            exit_code = 1

    return exit_code


def _run_query_mode(cli, query):
    """Execute a single query and print the result.

    Returns:
        Exit code: 0 if successful, 1 if failed.
    """
    success, output = cli.execute(query)

    if success:
        print(output)
        return 0
    else:
        print("ERROR: {}".format(output), file=sys.stderr)
        return 1


def _run_dump_help_mode(cli, path):
    """Execute debug commands to generate CLI help dump on the server.

    Returns:
        Exit code: 0 if successful, 1 if failed.
    """
    commands = [
        "ENTER DEBUG",
        "EXEC listCliHelp {}".format(path),
        "QUIT DEBUG",
    ]

    results = cli.execute_sequence(commands, stop_on_error=True)
    exit_code = 0

    for cmd, success, output in results:
        status = "OK" if success else "ERR"
        print(">>> {}".format(cmd))
        print("[{}] {}".format(status, output))
        print()
        if not success:
            exit_code = 1

    if exit_code == 0:
        print("CLI help dump generated on server at: {}".format(path))
        print("Retrieve it with: scp <server>:{} .".format(path))

    return exit_code


def _run_stdin_mode(cli):
    """Read commands from stdin and execute them one by one.

    Returns:
        Exit code: 0 if all succeeded, 1 if any failed.
    """
    exit_code = 0

    for line in sys.stdin:
        cmd = line.strip()
        if not cmd or cmd.startswith('#'):
            continue

        success, output = cli.execute(cmd)
        status = "OK" if success else "ERR"
        print(">>> {}".format(cmd))
        print("[{}] {}".format(status, output))
        print()

        if not success:
            exit_code = 1
            break

    return exit_code


if __name__ == '__main__':
    sys.exit(main() or 0)
