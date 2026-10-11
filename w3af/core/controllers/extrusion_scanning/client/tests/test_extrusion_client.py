import socket
import unittest

from w3af.core.controllers.extrusion_scanning.client.extrusion_client import (
    extrusionClient,
)


class TestExtrusionClient(unittest.TestCase):
    def test_sends_empty_udp_datagram_and_closes_socket(self):
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1)
        self.addCleanup(receiver.close)

        port = receiver.getsockname()[1]
        extrusionClient("127.0.0.1", [], [port]).start()

        payload, _ = receiver.recvfrom(1)
        self.assertEqual(payload, b"")

    def test_connects_to_tcp_listener_and_closes_socket(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(1)
        self.addCleanup(listener.close)

        port = listener.getsockname()[1]
        extrusionClient("127.0.0.1", [port], []).start()

        connection, _ = listener.accept()
        connection.close()
