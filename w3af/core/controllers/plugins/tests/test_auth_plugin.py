import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.plugins.auth_plugin import AuthPlugin
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.config import Config
from w3af.core.data.kb.knowledge_base import kb
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.helpers import new_no_content_resp
from w3af.core.data.url.http_response import HTTPResponse

LOGIN_URL = URL("http://127.0.0.1/login?next=/home")


class unit_auth(AuthPlugin):
    def __init__(self):
        super().__init__()
        self.set_configuration(cf)
        self.set_output(om.out)
        self.set_knowledge_base(kb)

    def _get_main_authentication_url(self):
        return LOGIN_URL


def response_with_id(response_id):
    response = HTTPResponse(200, "<html>body</html>", Headers(), LOGIN_URL, LOGIN_URL)
    response.id = response_id
    return response


class AuthPluginTestCase(unittest.TestCase):
    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)

        previous_blacklist = cf.get("blacklist_audit")
        cf.save("blacklist_audit", [])
        self.addCleanup(cf.save, "blacklist_audit", previous_blacklist)

    @staticmethod
    def authentication_errors():
        return kb.get("authentication", "error")


class TestNotImplementedMethods(unittest.TestCase):
    def test_login_logout_and_session_check_must_be_implemented(self):
        plugin = AuthPlugin()

        self.assertRaises(NotImplementedError, plugin.login)
        self.assertRaises(NotImplementedError, plugin.logout)
        self.assertRaises(NotImplementedError, plugin.has_active_session)
        self.assertRaises(NotImplementedError, plugin._get_main_authentication_url)

    def test_type_is_auth(self):
        self.assertEqual(AuthPlugin().get_type(), "auth")


class TestAuditBlacklist(AuthPluginTestCase):
    def test_login_urls_are_added_without_query_string(self):
        recorder = start_recording_output()

        unit_auth()._configure_audit_blacklist(
            URL("http://127.0.0.1/login?next=/home"), URL("http://127.0.0.1/auth")
        )

        blacklist = [str(url) for url in cf.get("blacklist_audit")]
        self.assertEqual(blacklist, ["http://127.0.0.1/login", "http://127.0.0.1/auth"])
        message = recorder.messages_of("information")[0]
        self.assertIn(" - http://127.0.0.1/login\n - http://127.0.0.1/auth", message)

    def test_urls_that_are_already_blacklisted_are_ignored(self):
        plugin = unit_auth()
        recorder = start_recording_output()
        plugin._configure_audit_blacklist(URL("http://127.0.0.1/login"))

        plugin._configure_audit_blacklist(URL("http://127.0.0.1/login?again=1"))

        self.assertEqual(len(cf.get("blacklist_audit")), 1)
        self.assertEqual(len(recorder.messages_of("information")), 1)

    def test_missing_blacklist_is_created(self):
        cf.save("blacklist_audit", None)

        unit_auth()._configure_audit_blacklist(URL("http://127.0.0.1/login"))

        self.assertEqual(len(cf.get("blacklist_audit")), 1)


class TestHttpResponseLog(AuthPluginTestCase):
    def test_responses_are_logged_by_id(self):
        plugin = unit_auth()

        self.assertTrue(plugin._log_http_response(response_with_id(7)))
        self.assertTrue(plugin._log_http_response(response_with_id(9)))

        self.assertEqual(plugin._http_response_ids, [7, 9])

    def test_no_content_responses_are_not_logged(self):
        plugin = unit_auth()

        self.assertFalse(plugin._log_http_response(new_no_content_resp(LOGIN_URL)))

        self.assertEqual(plugin._http_response_ids, [])

    def test_clear_log_forgets_responses_and_messages(self):
        plugin = unit_auth()
        plugin._log_http_response(response_with_id(7))
        plugin._log_debug("something")

        plugin._clear_log()

        self.assertEqual(plugin._http_response_ids, [])
        self.assertEqual(plugin._log_messages, [])


class TestLogMessages(AuthPluginTestCase):
    def test_debug_messages_are_formatted_with_plugin_and_debugging_id(self):
        plugin = unit_auth()
        plugin._set_debugging_id("abc123")
        recorder = start_recording_output()

        plugin._log_debug("trying to login")

        self.assertEqual(plugin._log_messages, ["trying to login"])
        self.assertEqual(
            recorder.messages_of("debug"),
            ["[auth.unit_auth] trying to login (did: abc123)"],
        )

    def test_error_messages_are_sent_as_is_and_also_logged_as_debug(self):
        plugin = unit_auth()
        plugin._set_debugging_id("abc123")
        recorder = start_recording_output()

        plugin._log_error("login failed")

        self.assertEqual(recorder.messages_of("error"), ["login failed"])
        self.assertEqual(
            recorder.messages_of("debug"),
            ["[auth.unit_auth] login failed (did: abc123)"],
        )
        self.assertEqual(plugin._log_messages, ["login failed", "login failed"])

    def test_debugging_id_is_kept_when_provided(self):
        plugin = unit_auth()

        plugin._set_debugging_id("fixed-id")

        self.assertEqual(plugin._debugging_id, "fixed-id")

    def test_random_debugging_id_is_generated_when_missing(self):
        plugin = unit_auth()

        plugin._set_debugging_id(None)

        self.assertRegex(plugin._debugging_id, r"^[a-zA-Z0-9]{8}$")


class TestLoginResults(AuthPluginTestCase):
    def failures(self, plugin, count):
        for _ in range(count):
            plugin._handle_authentication_failure()

    def test_few_failures_do_not_exceed_the_limit(self):
        plugin = unit_auth()

        self.failures(plugin, 2)

        self.assertFalse(plugin._max_consecutive_failed_login_count_exceeded())
        self.assertTrue(plugin._attempt_login)
        self.assertEqual(self.authentication_errors(), [])

    def test_consecutive_failures_disable_the_plugin_and_report_to_the_kb(self):
        plugin = unit_auth()
        plugin._set_debugging_id("abc123")
        plugin._log_debug("login attempt")
        recorder = start_recording_output()

        self.failures(plugin, 3)

        self.assertTrue(plugin._max_consecutive_failed_login_count_exceeded())
        self.assertFalse(plugin._attempt_login)
        info = self.authentication_errors()[0]
        self.assertEqual(info.get_name(), "Authentication failure")
        self.assertEqual(info.get_uri().url_string, LOGIN_URL.url_string)
        self.assertIn("failed 3 consecutive times", info.get_desc())
        self.assertIn("The following are the last log messages", info.get_desc())
        self.assertIn(" - login attempt", info.get_desc())
        self.assertIn("will be disabled", recorder.messages_of("error")[0])

    def test_a_success_between_failures_resets_the_consecutive_count(self):
        plugin = unit_auth()
        self.failures(plugin, 2)
        plugin._handle_authentication_success()

        self.failures(plugin, 2)

        self.assertFalse(plugin._max_consecutive_failed_login_count_exceeded())
        self.assertTrue(plugin._attempt_login)

    def test_all_attempts_failed_only_without_successes(self):
        plugin = unit_auth()
        self.failures(plugin, 1)
        self.assertTrue(plugin._all_login_attempts_failed())

        plugin._handle_authentication_success()

        self.assertFalse(plugin._all_login_attempts_failed())


class TestEnd(AuthPluginTestCase):
    def test_end_reports_when_the_plugin_never_authenticated(self):
        plugin = unit_auth()
        plugin._handle_authentication_failure()
        recorder = start_recording_output()

        plugin.end()

        self.assertFalse(plugin._attempt_login)
        info = self.authentication_errors()[0]
        self.assertIn("was never able to authenticate", info.get_desc())
        self.assertIn("never able to authenticate", recorder.messages_of("error")[0])

    def test_end_is_silent_after_a_successful_login(self):
        plugin = unit_auth()
        plugin._handle_authentication_success()

        plugin.end()

        self.assertTrue(plugin._attempt_login)
        self.assertEqual(self.authentication_errors(), [])


class TestKnowledgeBaseReport(AuthPluginTestCase):
    def test_report_without_log_messages_only_has_the_message(self):
        plugin = unit_auth()
        plugin._log_debug("not included")

        plugin._log_info_to_kb(
            "Authentication failure",
            "the authentication failed message",
            include_log_messages=False,
        )

        info = self.authentication_errors()[0]
        self.assertEqual(
            info.get_desc(with_id=False), "the authentication failed message"
        )

    def test_report_includes_the_response_ids(self):
        plugin = unit_auth()
        plugin._log_http_response(response_with_id(11))

        plugin._log_info_to_kb(
            "Authentication failure", "the authentication failed message"
        )

        self.assertEqual(self.authentication_errors()[0].get_id(), [11])


cf = Config()
