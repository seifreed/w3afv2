import unittest

from w3af.core.data.url.handlers.keepalive.connection_manager import ConnectionManager
from w3af.core.data.url.handlers.keepalive.connections import HTTPConnection


class TestConnectionManagerLogging(unittest.TestCase):
    def test_stats_sort_active_connections_by_request_start(self):
        connection_manager = ConnectionManager()
        connection_manager.LOG_STATS_EVERY = 1
        earlier_connection = HTTPConnection("example.test")
        later_connection = HTTPConnection("example.test")
        earlier_connection.current_request_start = 10.0
        later_connection.current_request_start = 20.0
        connection_manager._used_conns.update((later_connection, earlier_connection))

        with self.assertLogs(
            "w3af.core.data.url.handlers.keepalive.connection_manager",
            level="DEBUG",
        ) as records:
            connection_manager.log_stats("example.test:80")

        connection_info = next(
            record.getMessage()
            for record in records.records
            if "Connections with more in use time" in record.getMessage()
        )
        self.assertLess(
            connection_info.index(repr(earlier_connection.id)),
            connection_info.index(repr(later_connection.id)),
        )
