import socket
import unittest

from w3af.core.controllers.w3afAgent.client.w3af_agent_client import (
    COMMAND_CONNECT,
    ConnectionManager,
    Request_Bad_Version,
    Request_Invalid_Format,
    Request_Invalid_Port,
    Request_Unknown_Command,
    SocksHandler,
    port2string,
)


class TestW3afAgentClient(unittest.TestCase):
    def test_decode_request_returns_a_typed_socks_request(self):
        request = bytes((4, COMMAND_CONNECT))
        request += port2string(443)
        request += socket.inet_aton("198.51.100.10")
        request += b"w3af\x00"

        self.assertEqual(
            ConnectionManager.decode_request(request),
            {
                "version": 4,
                "command": COMMAND_CONNECT,
                "address": ("198.51.100.10", 443),
                "userid": b"w3af",
            },
        )

    def test_decode_request_rejects_malformed_frames(self):
        with self.assertRaises(Request_Invalid_Format):
            ConnectionManager.decode_request(b"short")

        valid_header = bytes((4, COMMAND_CONNECT)) + port2string(443)
        valid_header += socket.inet_aton("198.51.100.10") + b"\x00"

        with self.assertRaises(Request_Bad_Version):
            ConnectionManager.decode_request(b"\x05" + valid_header[1:])

        with self.assertRaises(Request_Unknown_Command):
            ConnectionManager.decode_request(bytes((4, 9)) + valid_header[2:])

        with self.assertRaises(Request_Invalid_Port):
            ConnectionManager.decode_request(
                bytes((4, COMMAND_CONNECT)) + b"\x00\x00" + valid_header[4:]
            )

    def test_answer_writes_a_binary_socks_reply(self):
        client, server = socket.socketpair()
        try:
            handler = SocksHandler(client, {})
            handler.answer(ip_str="198.51.100.20", port_int=8080)

            self.assertEqual(
                server.recv(8),
                b"\x00\x5a" + port2string(8080) + socket.inet_aton("198.51.100.20"),
            )
        finally:
            client.close()
            server.close()


if __name__ == "__main__":
    unittest.main()
