import unittest
from urllib.request import Request

from w3af.core.exceptions import (
    BaseFrameworkException,
    BodyCutException,
    FileException,
    ScanMustStopByKnownReasonExc,
    ScanMustStopByUnknownReasonExc,
    ScanMustStopByUserRequest,
    ScanMustStopException,
    ScanMustStopOnUrlError,
)


class TestFrameworkExceptions(unittest.TestCase):
    def test_base_exception_keeps_message(self):
        exception = BaseFrameworkException("failure")

        self.assertEqual(str(exception), "failure")
        self.assertIsInstance(BodyCutException("cut"), BaseFrameworkException)

    def test_file_exception_is_a_framework_exception(self):
        exception = FileException("file operation failed")

        self.assertIsInstance(exception, BaseFrameworkException)
        self.assertEqual(str(exception), "file operation failed")

    def test_scan_stop_includes_logged_errors(self):
        exception = ScanMustStopException("stopped", ("first", "second"))

        self.assertEqual(
            str(exception),
            "stopped The following errors were logged:\n  - first  - second",
        )
        self.assertEqual(repr(exception), str(exception))

    def test_scan_stop_without_errors_keeps_message(self):
        self.assertEqual(str(ScanMustStopException("stopped")), "stopped")

    def test_user_request_is_a_scan_stop(self):
        exception = ScanMustStopByUserRequest("user stopped")

        self.assertIsInstance(exception, ScanMustStopException)
        self.assertEqual(str(exception), "user stopped")

    def test_url_error_uses_real_url(self):
        request = Request("http://example.com/path")
        exception = ScanMustStopOnUrlError("connection failed", request)

        self.assertEqual(
            str(exception),
            "Extended URL library error 'connection failed' while requesting 'http://example.com/path'.",
        )
        self.assertEqual(repr(exception), str(exception))

    def test_known_reason_includes_reason_and_errors(self):
        exception = ScanMustStopByKnownReasonExc(
            "stopped", errs=("failure",), reason="network unavailable"
        )

        self.assertEqual(
            str(exception),
            "stopped The following errors were logged:\n  - failure - Reason: network unavailable",
        )

    def test_known_reason_without_reason(self):
        self.assertEqual(str(ScanMustStopByKnownReasonExc("stopped")), "stopped")

    def test_unknown_reason_lists_errors(self):
        exception = ScanMustStopByUnknownReasonExc("stopped", ("first", "second"))

        self.assertEqual(str(exception), "stopped\nfirst\nsecond")
