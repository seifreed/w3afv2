"""Tests for server connection ownership."""

import socket
import threading
import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.w3afAgent.server.w3af_agent_server import ConnectionManager


class TestConnectionManager(unittest.TestCase):
    def test_stop_closes_active_connections(self):
        client, server = socket.socketpair()
        try:
            manager = object.__new__(ConnectionManager)
            manager._keep_running = True
            manager._ip_address = "127.0.0.1"
            manager._port = 1
            manager._output = om.out
            manager._connections = [client]
            manager._cmLock = threading.RLock()

            manager.stop()

            self.assertEqual(server.recv(1), b"")
        finally:
            server.close()
