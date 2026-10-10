import logging
import queue
import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.output_manager.logging_bridge import (
    OutputManagerLogHandler,
    configure_data_logging,
)


class TestOutputManagerLoggingBridge(unittest.TestCase):
    def test_http_logger_uses_the_current_output_sink(self):
        previous_output = om.out
        messages = queue.Queue()
        om.out = om.log_sink_factory(messages)

        try:
            om.out.log_http("request", "response")
            self.assertEqual(
                messages.get(timeout=1), (("log_http", "request", "response"), {})
            )
        finally:
            om.out = previous_output

    def test_data_logs_reach_output_manager_once_at_their_severity(self):
        logger = logging.getLogger("w3af.core.data")
        previous_handlers = logger.handlers[:]
        previous_level = logger.level
        previous_propagate = logger.propagate
        previous_output = om.out
        messages = queue.Queue()
        om.out = om.log_sink_factory(messages)

        try:
            configure_data_logging(om.out)
            configure_data_logging(om.out)

            self.assertEqual(
                sum(
                    isinstance(handler, OutputManagerLogHandler)
                    for handler in logger.handlers
                ),
                1,
            )

            test_logger = logging.getLogger("w3af.core.data.logging_bridge_test")
            expected = (
                (logging.DEBUG, "debug", "debug message"),
                (logging.INFO, "information", "info message"),
                (logging.WARNING, "information", "warning message"),
                (logging.ERROR, "error", "error message"),
            )
            for level, method, message in expected:
                test_logger.log(level, "%s", message)
                self.assertEqual(messages.get(timeout=1), ((method, message), {}))
        finally:
            logger.handlers[:] = previous_handlers
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate
            om.out = previous_output

    def test_reconfiguring_logging_uses_the_new_output_sink(self):
        logger = logging.getLogger("w3af.core.data")
        previous_handlers = logger.handlers[:]
        previous_level = logger.level
        previous_propagate = logger.propagate
        first_messages = queue.Queue()
        second_messages = queue.Queue()

        try:
            configure_data_logging(om.log_sink_factory(first_messages))
            configure_data_logging(om.log_sink_factory(second_messages))

            logger.error("message for the second sink")

            self.assertEqual(
                second_messages.get(timeout=1),
                (("error", "message for the second sink"), {}),
            )
            self.assertTrue(first_messages.empty())
        finally:
            logger.handlers[:] = previous_handlers
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate
