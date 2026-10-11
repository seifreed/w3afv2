"""Tests for the local resources used by the agent manager."""

import socket
import unittest

from w3af.core.controllers.w3afAgent.w3af_agent_manager import w3afAgentManager


class TestW3afAgentManager(unittest.TestCase):
    def test_is_locally_available_closes_and_checks_real_sockets(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied_socket:
            occupied_socket.bind(("127.0.0.1", 0))
            occupied_socket.listen(1)
            port = occupied_socket.getsockname()[1]

            self.assertFalse(w3afAgentManager._is_locally_available(port))

        self.assertTrue(w3afAgentManager._is_locally_available(port))
