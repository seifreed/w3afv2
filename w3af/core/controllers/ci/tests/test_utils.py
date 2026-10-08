import logging
import unittest
from contextlib import redirect_stdout
from io import StringIO

from w3af.core.controllers.ci.utils import ColorLog


class TestColorLog(unittest.TestCase):
    def test_known_levels_emit_their_message(self):
        for level in (
            logging.CRITICAL,
            logging.ERROR,
            logging.WARNING,
            logging.INFO,
        ):
            output = StringIO()
            record = logging.LogRecord("test", level, "", 0, "message", (), None)

            with redirect_stdout(output):
                ColorLog().emit(record)

            self.assertIn("message", output.getvalue())

    def test_unmapped_level_emits_plain_message(self):
        output = StringIO()
        record = logging.LogRecord("test", logging.DEBUG, "", 0, "debug", (), None)

        with redirect_stdout(output):
            ColorLog().emit(record)

        self.assertEqual(output.getvalue(), "debug\n")
