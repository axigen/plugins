"""Tests for axigen_cli.py - Axigen CLI helper script.

Tests cover:
- parse_response() for +OK and -ERR lines
- AxigenCLI.connect() authentication flow with mock socket
- AxigenCLI.execute() returning success/failure
- AxigenCLI.execute_sequence() with stop_on_error behavior
- AxigenCLI.disconnect() sending QUIT
- main() argument parsing and modes
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call

# Add the skills/axigen-cli directory to the path so we can import axigen_cli
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'axigen-cli'))

from axigen_cli import parse_response, AxigenCLI


class TestParseResponse(unittest.TestCase):
    """Tests for the parse_response() function."""

    def test_ok_with_message(self):
        """parse_response should return (True, message) for +OK lines."""
        success, message = parse_response("+OK: Authentication successful")
        self.assertTrue(success)
        self.assertEqual(message, "Authentication successful")

    def test_err_with_message(self):
        """parse_response should return (False, message) for -ERR lines."""
        success, message = parse_response("-ERR: Unknown command")
        self.assertFalse(success)
        self.assertEqual(message, "Unknown command")

    def test_ok_without_message(self):
        """parse_response should return (True, '') for bare +OK."""
        success, message = parse_response("+OK")
        self.assertTrue(success)
        self.assertEqual(message, "")

    def test_err_without_message(self):
        """parse_response should return (False, '') for bare -ERR."""
        success, message = parse_response("-ERR")
        self.assertFalse(success)
        self.assertEqual(message, "")

    def test_ok_with_extra_whitespace(self):
        """parse_response should handle leading/trailing whitespace."""
        success, message = parse_response("  +OK: Done  ")
        self.assertTrue(success)
        self.assertEqual(message, "Done")

    def test_unrecognized_line(self):
        """parse_response should return (False, line) for unrecognized lines."""
        success, message = parse_response("some random text")
        self.assertFalse(success)
        self.assertEqual(message, "some random text")


class TestAxigenCLIConnect(unittest.TestCase):
    """Tests for AxigenCLI.connect() authentication flow."""

    @patch('axigen_cli.socket.socket')
    def test_connect_auth_flow(self, mock_socket_cls):
        """connect() should perform full auth: read banner, send user, send password."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        # Simulate the server responses during authentication:
        # 1. Welcome banner ending with <login> prompt
        # 2. After sending "user admin", server sends <password> prompt
        # 3. After sending password, server sends +OK and <#> prompt
        mock_sock.recv.side_effect = [
            b"Welcome to Axigen CLI\r\n<login> ",
            b"+OK: User accepted\r\n<password> ",
            b"+OK: Authentication successful\r\n<#> ",
        ]

        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        cli.connect()

        # Verify socket was created and connected
        mock_sock.connect.assert_called_once_with(("mail.example.com", 7000))
        mock_sock.settimeout.assert_called_with(30)

        # Verify the auth sequence: user command then password
        calls = mock_sock.sendall.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], call(b"user admin\r\n"))
        self.assertEqual(calls[1], call(b"secret123\r\n"))

    @patch('axigen_cli.socket.socket')
    def test_connect_auth_failure(self, mock_socket_cls):
        """connect() should raise an exception if authentication fails."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        mock_sock.recv.side_effect = [
            b"Welcome to Axigen CLI\r\n<login> ",
            b"+OK: User accepted\r\n<password> ",
            b"-ERR: Authentication failed\r\n<login> ",
        ]

        cli = AxigenCLI("mail.example.com", 7000, "admin", "wrongpass")
        with self.assertRaises(Exception) as ctx:
            cli.connect()
        self.assertIn("Authentication failed", str(ctx.exception))


class TestAxigenCLIExecute(unittest.TestCase):
    """Tests for AxigenCLI.execute() command execution."""

    def _make_connected_cli(self, mock_socket_cls):
        """Helper: create an AxigenCLI with a mocked, already-connected socket."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        # Auth flow responses
        mock_sock.recv.side_effect = [
            b"Welcome to Axigen CLI\r\n<login> ",
            b"+OK: User accepted\r\n<password> ",
            b"+OK: Authentication successful\r\n<#> ",
        ]

        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        cli.connect()

        # Reset mock so we can track only execute() calls
        mock_sock.reset_mock()
        return cli, mock_sock

    @patch('axigen_cli.socket.socket')
    def test_execute_success(self, mock_socket_cls):
        """execute() should return (True, output) on +OK response."""
        cli, mock_sock = self._make_connected_cli(mock_socket_cls)

        mock_sock.recv.side_effect = [
            b"+OK: domain1.com\r\ndomain2.com\r\n<#> ",
        ]

        success, output = cli.execute("LIST Domains")

        mock_sock.sendall.assert_called_once_with(b"LIST Domains\r\n")
        self.assertTrue(success)
        self.assertIn("domain1.com", output)

    @patch('axigen_cli.socket.socket')
    def test_execute_failure(self, mock_socket_cls):
        """execute() should return (False, output) on -ERR response."""
        cli, mock_sock = self._make_connected_cli(mock_socket_cls)

        mock_sock.recv.side_effect = [
            b"-ERR: Domain not found\r\n<#> ",
        ]

        success, output = cli.execute("UPDATE Domain nonexistent.com")

        self.assertFalse(success)
        self.assertIn("Domain not found", output)

    @patch('axigen_cli.socket.socket')
    def test_execute_multipart_recv(self, mock_socket_cls):
        """execute() should handle responses split across multiple recv() calls."""
        cli, mock_sock = self._make_connected_cli(mock_socket_cls)

        # Response arrives in two parts
        mock_sock.recv.side_effect = [
            b"+OK: partial",
            b" response\r\n<#> ",
        ]

        success, output = cli.execute("SHOW")

        self.assertTrue(success)
        self.assertIn("partial response", output)


class TestAxigenCLIExecuteSequence(unittest.TestCase):
    """Tests for AxigenCLI.execute_sequence()."""

    @patch('axigen_cli.socket.socket')
    def test_execute_sequence_all_success(self, mock_socket_cls):
        """execute_sequence() should execute all commands when all succeed."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        # Auth flow
        mock_sock.recv.side_effect = [
            b"Welcome\r\n<login> ",
            b"+OK\r\n<password> ",
            b"+OK: Authentication successful\r\n<#> ",
            # Command 1
            b"+OK: Done\r\n<#> ",
            # Command 2
            b"+OK: Done\r\n<#> ",
        ]

        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        cli.connect()

        results = cli.execute_sequence(["CMD1", "CMD2"])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], "CMD1")
        self.assertTrue(results[0][1])
        self.assertEqual(results[1][0], "CMD2")
        self.assertTrue(results[1][1])

    @patch('axigen_cli.socket.socket')
    def test_execute_sequence_stop_on_error(self, mock_socket_cls):
        """execute_sequence() should stop on first error when stop_on_error=True."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        mock_sock.recv.side_effect = [
            b"Welcome\r\n<login> ",
            b"+OK\r\n<password> ",
            b"+OK: Authentication successful\r\n<#> ",
            # Command 1 fails
            b"-ERR: Failed\r\n<#> ",
            # Command 2 should NOT be executed
        ]

        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        cli.connect()

        results = cli.execute_sequence(["CMD1", "CMD2", "CMD3"], stop_on_error=True)

        # Only the first (failing) command should be in results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "CMD1")
        self.assertFalse(results[0][1])

    @patch('axigen_cli.socket.socket')
    def test_execute_sequence_continue_on_error(self, mock_socket_cls):
        """execute_sequence() should continue past errors when stop_on_error=False."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        mock_sock.recv.side_effect = [
            b"Welcome\r\n<login> ",
            b"+OK\r\n<password> ",
            b"+OK: Authentication successful\r\n<#> ",
            # Command 1 fails
            b"-ERR: Failed\r\n<#> ",
            # Command 2 succeeds
            b"+OK: Done\r\n<#> ",
        ]

        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        cli.connect()

        results = cli.execute_sequence(["CMD1", "CMD2"], stop_on_error=False)

        self.assertEqual(len(results), 2)
        self.assertFalse(results[0][1])
        self.assertTrue(results[1][1])


class TestAxigenCLIDisconnect(unittest.TestCase):
    """Tests for AxigenCLI.disconnect()."""

    @patch('axigen_cli.socket.socket')
    def test_disconnect_sends_quit(self, mock_socket_cls):
        """disconnect() should send QUIT and close the socket."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        # Auth flow
        mock_sock.recv.side_effect = [
            b"Welcome\r\n<login> ",
            b"+OK\r\n<password> ",
            b"+OK: Authentication successful\r\n<#> ",
        ]

        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        cli.connect()
        mock_sock.reset_mock()

        # For disconnect, the server may send a farewell or just close.
        # We'll let recv return empty to simulate connection close.
        mock_sock.recv.side_effect = [b"+OK: Goodbye\r\n"]

        cli.disconnect()

        mock_sock.sendall.assert_called_with(b"QUIT\r\n")
        mock_sock.close.assert_called_once()

    @patch('axigen_cli.socket.socket')
    def test_disconnect_without_connect(self, mock_socket_cls):
        """disconnect() should not raise if never connected."""
        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        # Should not raise
        cli.disconnect()


class TestAxigenCLIRecvUntilPrompt(unittest.TestCase):
    """Tests for AxigenCLI._recv_until_prompt()."""

    @patch('axigen_cli.socket.socket')
    def test_recv_detects_login_prompt(self, mock_socket_cls):
        """_recv_until_prompt() should detect <login> prompt."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.recv.side_effect = [b"Welcome to Axigen\r\n<login> "]

        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        cli._sock = mock_sock

        data = cli._recv_until_prompt()
        self.assertIn("<login>", data)

    @patch('axigen_cli.socket.socket')
    def test_recv_detects_domain_prompt(self, mock_socket_cls):
        """_recv_until_prompt() should detect domain context prompts like <domain#>."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.recv.side_effect = [b"+OK\r\n<domain#> "]

        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        cli._sock = mock_sock

        data = cli._recv_until_prompt()
        self.assertIn("<domain#>", data)

    @patch('axigen_cli.socket.socket')
    def test_recv_accumulates_fragments(self, mock_socket_cls):
        """_recv_until_prompt() should accumulate data across multiple recv() calls."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.recv.side_effect = [
            b"+OK: Line 1\r\n",
            b"Line 2\r\n",
            b"<#> ",
        ]

        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        cli._sock = mock_sock

        data = cli._recv_until_prompt()
        self.assertIn("Line 1", data)
        self.assertIn("Line 2", data)
        self.assertIn("<#>", data)


class TestAxigenCLISend(unittest.TestCase):
    """Tests for AxigenCLI._send()."""

    @patch('axigen_cli.socket.socket')
    def test_send_appends_crlf(self, mock_socket_cls):
        """_send() should append CRLF and call sendall."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        cli = AxigenCLI("mail.example.com", 7000, "admin", "secret123")
        cli._sock = mock_sock

        cli._send("HELP")

        mock_sock.sendall.assert_called_once_with(b"HELP\r\n")


class TestMain(unittest.TestCase):
    """Tests for main() argument parsing and modes."""

    @patch('axigen_cli.AxigenCLI')
    def test_main_commands_mode(self, mock_cli_cls):
        """main() with --commands should execute command sequence."""
        mock_cli = MagicMock()
        mock_cli_cls.return_value = mock_cli
        mock_cli.execute_sequence.return_value = [
            ("LIST Domains", True, "+OK: domain1.com"),
        ]

        test_args = [
            'axigen_cli.py',
            '--host', 'mail.example.com',
            '--password', 'secret',
            '--commands', 'LIST Domains',
        ]

        with patch('sys.argv', test_args):
            from axigen_cli import main
            exit_code = main()

        mock_cli_cls.assert_called_once()
        mock_cli.connect.assert_called_once()
        mock_cli.execute_sequence.assert_called_once_with(["LIST Domains"], stop_on_error=True)
        mock_cli.disconnect.assert_called_once()
        self.assertEqual(exit_code, 0)

    @patch('axigen_cli.AxigenCLI')
    def test_main_query_mode(self, mock_cli_cls):
        """main() with --query should execute a single command."""
        mock_cli = MagicMock()
        mock_cli_cls.return_value = mock_cli
        mock_cli.execute.return_value = (True, "+OK: domain1.com")

        test_args = [
            'axigen_cli.py',
            '--host', 'mail.example.com',
            '--password', 'secret',
            '--query', 'LIST Domains',
        ]

        with patch('sys.argv', test_args):
            from axigen_cli import main
            exit_code = main()

        mock_cli.execute.assert_called_once_with("LIST Domains")
        self.assertEqual(exit_code, 0)

    @patch('axigen_cli.AxigenCLI')
    def test_main_query_failure_returns_1(self, mock_cli_cls):
        """main() should return exit code 1 when a query fails."""
        mock_cli = MagicMock()
        mock_cli_cls.return_value = mock_cli
        mock_cli.execute.return_value = (False, "-ERR: Failed")

        test_args = [
            'axigen_cli.py',
            '--host', 'mail.example.com',
            '--password', 'secret',
            '--query', 'BAD COMMAND',
        ]

        with patch('sys.argv', test_args):
            from axigen_cli import main
            exit_code = main()

        self.assertEqual(exit_code, 1)

    @patch.dict(os.environ, {
        'AXIGEN_HOST': 'env-host.example.com',
        'AXIGEN_PORT': '7001',
        'AXIGEN_USER': 'envadmin',
        'AXIGEN_PASS': 'envsecret',
    })
    @patch('axigen_cli.AxigenCLI')
    def test_main_env_vars(self, mock_cli_cls):
        """main() should use environment variables as defaults."""
        mock_cli = MagicMock()
        mock_cli_cls.return_value = mock_cli
        mock_cli.execute.return_value = (True, "+OK")

        test_args = [
            'axigen_cli.py',
            '--query', 'HELP',
        ]

        with patch('sys.argv', test_args):
            from axigen_cli import main
            main()

        # Check the CLI was created with env var values
        call_kwargs = mock_cli_cls.call_args
        args = call_kwargs[0] if call_kwargs[0] else ()
        kwargs = call_kwargs[1] if call_kwargs[1] else {}

        # The constructor could be called positionally or with kwargs.
        # We check that the values from env vars were used.
        if args:
            self.assertEqual(args[0], 'env-host.example.com')
            self.assertEqual(args[1], 7001)
            self.assertEqual(args[2], 'envadmin')
            self.assertEqual(args[3], 'envsecret')
        else:
            self.assertEqual(kwargs.get('host'), 'env-host.example.com')
            self.assertEqual(kwargs.get('port'), 7001)

    @patch('axigen_cli.AxigenCLI')
    def test_main_dump_help_mode(self, mock_cli_cls):
        """main() with --dump-help should execute debug commands."""
        mock_cli = MagicMock()
        mock_cli_cls.return_value = mock_cli
        mock_cli.execute_sequence.return_value = [
            ("ENTER DEBUG", True, "+OK"),
            ("EXEC listCliHelp /tmp/cliHelp.txt", True, "+OK"),
            ("QUIT DEBUG", True, "+OK"),
        ]

        test_args = [
            'axigen_cli.py',
            '--host', 'mail.example.com',
            '--password', 'secret',
            '--dump-help', '/tmp/cliHelp.txt',
        ]

        with patch('sys.argv', test_args):
            from axigen_cli import main
            exit_code = main()

        mock_cli.connect.assert_called_once()
        # Should have executed a sequence containing the debug commands
        seq_call = mock_cli.execute_sequence.call_args
        commands = seq_call[0][0]
        self.assertIn("ENTER DEBUG", commands)
        self.assertTrue(any("listCliHelp" in c for c in commands))
        self.assertEqual(exit_code, 0)


if __name__ == '__main__':
    unittest.main()
