"""Tests for shared payload helpers."""

import unittest

from w3af.plugins.attack.payloads.payload_utils import (
    get_process_username,
    int_to_dotted_quad,
    parse_proc_net,
    split_proc_net_address,
)


class TestPayloadUtils(unittest.TestCase):
    def test_parse_proc_net(self):
        data = "  sl  local_address\n0: 0100007F:0016 00000000:0000\n"

        self.assertEqual(
            parse_proc_net(data),
            [["sl", "local_address"], ["0:", "0100007F:0016", "00000000:0000"]],
        )

    def test_get_process_username(self):
        passwd_data = "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin"

        self.assertEqual(get_process_username(passwd_data, "1"), "daemon")
        self.assertEqual(get_process_username(passwd_data, "99"), "")

    def test_split_proc_net_address(self):
        self.assertEqual(split_proc_net_address("0100007F:0016"), ["0100007F", "0016"])

    def test_int_to_dotted_quad(self):
        self.assertEqual(int_to_dotted_quad(0), "0.0.0.0")
        self.assertEqual(int_to_dotted_quad(0x0A000202), "10.0.2.2")
        self.assertEqual(int_to_dotted_quad(0xFFFFFFFF), "255.255.255.255")
