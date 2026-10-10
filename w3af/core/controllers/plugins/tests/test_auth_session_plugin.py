import threading
import unittest

from w3af.core.controllers.plugins.auth_session_plugin import AuthSessionPlugin
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.knowledge_base import kb
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.helpers import new_no_content_resp
from w3af.core.data.url.http_response import HTTPResponse

LOGGED_IN = "Welcome back pablo"
LOGGED_OUT = "Please login"


class unit_session_auth(AuthSessionPlugin):
    def __init__(self):
        super().__init__()
        self.set_knowledge_base(kb)

    def _get_main_authentication_url(self):
        return self.check_url


class SessionSite:
    """
    A real HTTP server that tells if the user is logged in, following the
    script of answers it was created with (the last answer is repeated).
    """

    def __init__(self, answers):
        self._answers = list(answers)
        self._lock = threading.Lock()
        self.server = LocalHTTPServer(self._respond).start()

    def _respond(self, method, path):
        with self._lock:
            answer = (
                self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
            )
        return Reply(body=answer)


class AuthSessionTestCase(unittest.TestCase):
    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)

    def plugin_for(self, answers):
        site = SessionSite(answers)
        self.addCleanup(site.server.close)

        uri_opener = ExtendedUrllib()
        self.addCleanup(uri_opener.end)
        self.addCleanup(uri_opener.settings.set_default_values)

        plugin = unit_session_auth()
        plugin.set_url_opener(uri_opener)
        plugin.username = "pablo"
        plugin.check_url = URL(site.server.url("/account"))
        plugin.check_string = "Welcome"
        return plugin, site

    def checks(self, plugin, count):
        return [plugin.has_active_session() for _ in range(count)]

    @staticmethod
    def authentication_errors():
        return kb.get("authentication", "error")


class TestHasActiveSession(AuthSessionTestCase):
    def test_logged_in_user(self):
        plugin, site = self.plugin_for([LOGGED_IN])
        recorder = start_recording_output()

        self.assertTrue(plugin.has_active_session())

        self.assertEqual(site.server.requested_paths, ["/account"])
        self.assertEqual(plugin._valid_sessions_count, 1)
        self.assertEqual(plugin._invalid_sessions_count, -1)
        self.assertTrue(
            any(
                'User "pablo" is currently logged into the application' in m
                for m in recorder.messages_of("debug")
            )
        )

    def test_user_that_is_not_logged_in(self):
        plugin, _ = self.plugin_for([LOGGED_OUT])
        recorder = start_recording_output()

        self.assertFalse(plugin.has_active_session())

        self.assertEqual(plugin._invalid_sessions_count, 0)
        self.assertTrue(
            any(
                'User "pablo" is NOT logged into the application' in m
                for m in recorder.messages_of("debug")
            )
        )

    def test_checked_responses_are_logged(self):
        plugin, _ = self.plugin_for([LOGGED_IN])

        plugin.has_active_session()

        self.assertEqual(len(plugin._http_response_ids), 1)
        self.assertEqual(
            plugin._session_failed_http_request_ids, plugin._http_response_ids
        )

    def test_debugging_id_can_be_provided_by_the_caller(self):
        plugin, _ = self.plugin_for([LOGGED_IN])

        plugin.has_active_session(debugging_id="caller-id")

        self.assertEqual(plugin._debugging_id, "caller-id")

    def test_no_requests_are_sent_after_the_plugin_gave_up(self):
        plugin, site = self.plugin_for([LOGGED_IN])
        plugin._attempt_login = False

        self.assertFalse(plugin.has_active_session())

        self.assertEqual(site.server.requested_paths, [])

    def test_request_errors_are_not_an_active_session(self):
        plugin, _ = self.plugin_for([LOGGED_IN])
        plugin.check_url = None
        recorder = start_recording_output()

        self.assertFalse(plugin.has_active_session())

        self.assertEqual(plugin._invalid_sessions_count, 0)
        self.assertTrue(
            any(
                "Failed to check if session is active" in m
                for m in recorder.messages_of("debug")
            )
        )


class TestInvalidSessionReport(AuthSessionTestCase):
    def test_unstable_sessions_are_reported_when_ending(self):
        # The first failed check is expected: the auth consumer checks the
        # session before logging in. Then 1 of the 19 checks fails
        # (5.26%), which is over the 5% limit
        plugin, _ = self.plugin_for([LOGGED_OUT, LOGGED_OUT] + [LOGGED_IN])
        self.checks(plugin, 20)
        plugin._handle_authentication_success()
        recorder = start_recording_output()

        plugin.end()

        info = self.authentication_errors()[0]
        self.assertEqual(info.get_name(), "Unstable application session")
        self.assertIn("session was lost 1 times", info.get_desc().replace("\n", " "))
        self.assertIn("(5%)", info.get_desc())
        self.assertEqual(info.get_uri().url_string, plugin.check_url.url_string)
        self.assertEqual(len(info.get_id()), 20)
        self.assertEqual(len(recorder.messages_of("error")), 1)

    def test_stable_sessions_are_not_reported(self):
        plugin, _ = self.plugin_for([LOGGED_OUT] + [LOGGED_IN])
        self.checks(plugin, 40)
        plugin._handle_authentication_success()

        plugin.end()

        self.assertEqual(self.authentication_errors(), [])

    def test_too_few_session_checks_are_not_reported(self):
        plugin, _ = self.plugin_for([LOGGED_OUT, LOGGED_OUT, LOGGED_IN])
        self.checks(plugin, 5)
        plugin._handle_authentication_success()

        plugin.end()

        self.assertEqual(self.authentication_errors(), [])

    def test_percentage_without_session_checks_is_zero(self):
        plugin, _ = self.plugin_for([LOGGED_IN])
        plugin.has_active_session()

        # One valid session and the initial "failed" check offset
        self.assertEqual(plugin._get_invalid_session_perc(), 0.0)

    def test_percentage_of_invalid_sessions(self):
        plugin, _ = self.plugin_for([LOGGED_OUT, LOGGED_OUT, LOGGED_IN])
        self.checks(plugin, 3)

        # -1 + 2 invalid and 1 valid
        self.assertEqual(plugin._get_invalid_session_perc(), 50.0)


class TestFailedResponseLog(AuthSessionTestCase):
    def test_responses_are_saved_by_id(self):
        plugin, _ = self.plugin_for([LOGGED_IN])
        response = HTTPResponse(
            200, "body", Headers(), plugin.check_url, plugin.check_url
        )
        response.id = 33

        self.assertTrue(plugin._log_session_failed_http_response(response))

        self.assertEqual(plugin._session_failed_http_request_ids, [33])

    def test_no_content_responses_are_not_saved(self):
        plugin, _ = self.plugin_for([LOGGED_IN])

        saved = plugin._log_session_failed_http_response(
            new_no_content_resp(plugin.check_url)
        )

        self.assertFalse(saved)
        self.assertEqual(plugin._session_failed_http_request_ids, [])
