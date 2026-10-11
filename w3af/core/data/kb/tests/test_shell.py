"""
test_shell.py

Copyright 2026 w3af contributors

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

import copy
import socket
import unittest

from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.kb.shell import NO_PAYLOAD_HANDLER_MSG, Shell
from w3af.core.data.kb.tests.local_shells import LocalExecShell, payload_catalog
from w3af.core.data.kb.tests.test_vuln import MockVuln


class PayloadExecShell(LocalExecShell):
    _payload_handler = payload_catalog()


class EchoShell(Shell):
    def specific_user_input(self, command, parameters):
        if command == "echo":
            return " ".join(parameters)


class TestShell(unittest.TestCase):
    def setUp(self):
        self.vuln = MockVuln()
        self.shell = Shell(self.vuln, "uri opener", "worker pool")

    def test_requires_a_vuln(self):
        self.assertRaises(TypeError, Shell, "not a vuln", None, None)

    def test_collaborators(self):
        self.assertEqual(self.shell.get_url_opener(), "uri opener")
        self.assertEqual(self.shell.worker_pool, "worker pool")

        self.shell.set_url_opener("other opener")
        self.assertEqual(self.shell.get_url_opener(), "other opener")

    def test_abstract_methods(self):
        self.assertRaises(NotImplementedError, self.shell.help, None)
        self.assertRaises(NotImplementedError, self.shell.get_name)
        self.assertRaises(NotImplementedError, self.shell.identify_os)
        self.assertRaises(NotImplementedError, repr, self.shell)

    def test_exploit_result_id(self):
        self.shell.set_exploit_result_id(3)

        self.assertEqual(self.shell._id, 3)

    def test_defaults(self):
        self.assertTrue(self.shell.end_interaction())
        self.assertIsNone(self.shell.end())
        self.assertIsNone(self.shell.specific_user_input("ls", []))
        self.assertEqual(self.shell.get_uniq_id(), self.vuln.get_uniq_id())

    def test_vuln_attributes_are_forwarded(self):
        self.shell["key"] = "value"

        self.assertEqual(self.shell["key"], "value")
        self.assertEqual(self.vuln["key"], "value")
        self.assertEqual(self.shell.get_severity(), self.vuln.get_severity())

    def test_magic_methods_are_not_forwarded(self):
        self.assertRaises(AttributeError, getattr, self.shell, "__missing__")

    def test_kb_round_trip_drops_collaborators(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)

        kb.append("a", "b", self.shell)
        (stored,) = kb.get("a", "b")

        self.assertEqual(stored, self.shell)
        self.assertIsNone(stored.get_url_opener())
        self.assertIsNone(stored.worker_pool)

    def test_subclasses_must_implement_reduce(self):
        shell = EchoShell(self.vuln, None, None)

        self.assertRaises(NotImplementedError, copy.copy, shell)

    def test_unknown_command(self):
        self.assertEqual(
            self.shell.generic_user_input("ls", []),
            'Command "ls" not found. Please type "help".',
        )

    def test_specific_command(self):
        shell = EchoShell(self.vuln, None, None)

        self.assertEqual(shell.generic_user_input("echo", ["a", "b"]), "a b")

    def test_payload_without_parameters(self):
        self.assertIsNone(self.shell.generic_user_input("payload", []))

    def test_without_payload_handler(self):
        self.assertEqual(
            self.shell.generic_user_input("payload", ["hostname"]),
            NO_PAYLOAD_HANDLER_MSG,
        )
        self.assertEqual(
            self.shell.generic_user_input("lsp", []), NO_PAYLOAD_HANDLER_MSG
        )


class TestShellPayloads(unittest.TestCase):
    def setUp(self):
        self.shell = PayloadExecShell(MockVuln(), None, None)
        self.handler = PayloadExecShell._payload_handler
        self.handler.executed.clear()

    def test_help_command(self):
        self.assertIn("Available commands", self.shell.generic_user_input("help", []))
        self.assertIn(
            "/tmp/passwd", self.shell.generic_user_input("help", ["download"])
        )

    def test_list_runnable_payloads(self):
        self.assertEqual(
            self.shell.generic_user_input("lsp", []),
            "hostname\nport_check\nread_users",
        )

    def test_payload_description(self):
        self.assertEqual(
            self.shell.generic_user_input("payload", ["desc", "hostname"]),
            "Show the hostname",
        )
        self.assertEqual(
            self.shell.generic_user_input("payload", ["desc", "unknown"]),
            'Unknown payload name: "unknown"',
        )

    def test_unknown_payload(self):
        self.assertEqual(
            self.shell.generic_user_input("payload", ["unknown"]),
            'Unknown payload name: "unknown"',
        )

    def test_run_payload(self):
        self.assertIsNone(self.shell.generic_user_input("payload", ["hostname"]))

        self.assertEqual(self.handler.executed, [("hostname", socket.gethostname())])

    def test_run_payload_reading_files(self):
        self.shell.generic_user_input("payload", ["read_users"])

        ((name, users),) = self.handler.executed
        self.assertEqual(name, "read_users")
        self.assertIn("root", users)

    def test_run_payload_with_wrong_parameter_count(self):
        result = self.shell.generic_user_input("payload", ["hostname", "extra"])

        self.assertEqual(result, "Show the hostname")

    def test_run_payload_with_invalid_parameter(self):
        result = self.shell.generic_user_input("payload", ["port_check", "http"])

        self.assertEqual(result, 'Invalid port "http".')

    def test_run_payload_with_valid_parameter(self):
        self.shell.generic_user_input("payload", ["port_check", "80"])

        self.assertEqual(self.handler.executed, [("port_check", 80)])

    def test_payload_without_required_capabilities(self):
        result = self.shell.generic_user_input("payload", ["screenshot"])

        self.assertEqual(
            result,
            "The payload could not be run because the current shell doesn't"
            " have the required capabilities.",
        )


kb = DBKnowledgeBase()
