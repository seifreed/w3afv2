"""
test_cli.py

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""

import contextlib
import hashlib
import io
import os
import tempfile
import unittest
from argparse import ArgumentTypeError

from flask import Flask

from w3af.core.ui.api.utils.cli import (
    build_parser,
    parse_arguments,
    parse_host_port,
    process_cmd_args_config,
)

PASSWORD_HASH = hashlib.sha512(b"secret").hexdigest()


class CLITest(unittest.TestCase):
    def setUp(self):
        self.app = Flask("cli-test")

    def configure(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            args = process_cmd_args_config(self.app, list(argv))
        return args, output.getvalue()

    def config_file(self, content):
        descriptor, path = tempfile.mkstemp(suffix=".yml")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_defaults(self):
        args, output = self.configure()

        self.assertEqual(self.app.config["HOST"], "127.0.0.1")
        self.assertEqual(self.app.config["PORT"], 5000)
        self.assertEqual(self.app.config["USERNAME"], "admin")
        self.assertFalse(self.app.config["DISABLE_SSL"])
        self.assertNotIn("PASSWORD", self.app.config)
        self.assertFalse(args.verbose)
        self.assertEqual(output, "")

    def test_command_line_options(self):
        self.configure("localhost:8080", "--no-ssl", "-p", PASSWORD_HASH, "-u", "bob")

        self.assertEqual(self.app.config["HOST"], "localhost")
        self.assertEqual(self.app.config["PORT"], 8080)
        self.assertEqual(self.app.config["PASSWORD"], PASSWORD_HASH)
        self.assertEqual(self.app.config["USERNAME"], "bob")
        self.assertTrue(self.app.config["DISABLE_SSL"])

    def test_public_bind_warnings(self):
        _, output = self.configure("0.0.0.0:8080")
        self.assertIn("basic authentication", output)
        self.assertIn("self-signed", output)

        self.app = Flask("cli-test")
        _, output = self.configure("0.0.0.0:8080", "--no-ssl", "-p", PASSWORD_HASH)
        self.assertNotIn("basic authentication", output)
        self.assertIn("not encrypted", output)

    def test_invalid_host_port(self):
        for argv in (["127.0.0.1"], ["127.0.0.1:http"], ["h:70000"]):
            with self.subTest(argv=argv), self.assertRaises(ArgumentTypeError):
                self.configure(*argv)

    def test_parse_host_port(self):
        self.assertEqual(parse_host_port("::1", "0"), ("::1", 0))
        for host, port in (("h", -1), ("", 5000)):
            with self.subTest(host=host, port=port), self.assertRaises(
                ArgumentTypeError
            ):
                parse_host_port(host, port)

    def test_invalid_passwords(self):
        for password in ("plain-text", "ab" * 10):
            with self.subTest(password=password), self.assertRaises(ArgumentTypeError):
                self.configure("-p", password)

    def test_config_file(self):
        path = self.config_file(
            f"host: 127.0.0.1\nport: 6000\npassword: {PASSWORD_HASH}\n"
            "username: alice\ndisable_ssl: true\nnested:\n  - ignored\n"
        )
        self.configure("-c", path)

        self.assertEqual(self.app.config["PORT"], 6000)
        self.assertEqual(self.app.config["USERNAME"], "alice")
        self.assertEqual(self.app.config["PASSWORD"], PASSWORD_HASH)
        self.assertTrue(self.app.config["DISABLE_SSL"])
        self.assertNotIn("NESTED", self.app.config)

    def test_config_file_conflicts_with_command_line(self):
        path = self.config_file("username: alice\n")
        with self.assertRaisesRegex(ArgumentTypeError, "conflicting options"):
            self.configure("-c", path, "-u", "bob")

    def test_invalid_config_files(self):
        paths = [
            self.config_file("key: [unclosed\n"),
            self.config_file("- just\n- a list\n"),
            os.path.join(tempfile.gettempdir(), "w3af-missing-config.yml"),
        ]
        for path in paths:
            with self.subTest(path=path), self.assertRaisesRegex(
                ArgumentTypeError, "Error loading config file"
            ):
                self.configure("-c", path)

    def test_custom_parser(self):
        parser = build_parser("Custom service")
        parser.add_argument("--extra", action="store_true")

        args = parse_arguments(["--extra"], parser)

        self.assertTrue(args.extra)
        self.assertEqual(parser.description, "Custom service")
