import os
import tempfile
import threading
import unittest

from w3af.core.controllers.plugins.bruteforce_plugin import BruteforcePlugin
from w3af.core.controllers.threads.threadpool import Pool
from w3af.core.data.constants import severity
from w3af.core.data.kb.knowledge_base import kb
from w3af.core.data.kb.vuln import Vuln
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest

TARGET = URL("http://www.example.com/login")


class unit_bruteforce(BruteforcePlugin):
    """
    Bruteforce plugin that reports a credential for every URL it audits and
    keeps track of what the worker pool asked it to try.
    """

    def __init__(self):
        BruteforcePlugin.__init__(self)
        self.set_knowledge_base(kb)
        self.tried = []
        self.audited = []
        self._lock = threading.Lock()

    def audit(self, freq, debugging_id=None):
        self.audited.append((freq, debugging_id))
        vuln = Vuln.from_fr(
            "Guessable credentials",
            "Credentials found by the unit test",
            severity.HIGH,
            [],
            self.get_name(),
            freq,
        )
        vuln["request"] = freq
        self._get_knowledge_base().append(self.get_name(), "auth", vuln)

    def _brute_worker(self, url, combination, debugging_id):
        with self._lock:
            self.tried.append((url, combination, debugging_id))


class BruteforcePluginTestCase(unittest.TestCase):
    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.users_file = self.write_lines(directory.name, "users.txt", ["root", "bob"])
        self.passwords_file = self.write_lines(
            directory.name, "passwords.txt", ["secret", "1234"]
        )

    @staticmethod
    def write_lines(directory, name, lines):
        path = os.path.join(directory, name)
        with open(path, "w") as lines_file:
            lines_file.write("\n".join(lines) + "\n")
        return path

    def plugin(self):
        """A plugin that only uses the files and options of the test"""
        plugin = unit_bruteforce()
        plugin._users_file = self.users_file
        plugin._passwd_file = self.passwords_file
        plugin._use_emails = False
        plugin._use_SVN_users = False
        plugin._pass_eq_user = False
        plugin._l337_p4sswd = False
        plugin._use_profiling = False
        return plugin


class TestNotImplementedMethods(unittest.TestCase):
    def test_subclasses_must_implement_the_bruteforce_logic(self):
        plugin = BruteforcePlugin()

        self.assertRaises(NotImplementedError, plugin.audit, None)
        self.assertRaises(NotImplementedError, plugin.end)
        self.assertRaises(NotImplementedError, plugin._brute_worker, "url", None, "id")


class TestPluginInformation(unittest.TestCase):
    def test_type_is_bruteforce(self):
        self.assertEqual(BruteforcePlugin().get_type(), "bruteforce")

    def test_plugin_dependencies(self):
        self.assertEqual(
            BruteforcePlugin().get_plugin_deps(),
            ["grep.password_profiling", "grep.get_emails", "grep.http_auth_detect"],
        )

    def test_long_description_lists_the_configurable_parameters(self):
        description = BruteforcePlugin().get_long_desc()

        for parameter in ("users_file", "passwd_file", "combo_file", "stop_on_first"):
            self.assertIn(parameter, description)

    def test_default_files_exist(self):
        plugin = BruteforcePlugin()

        for path in (plugin._users_file, plugin._passwd_file, plugin._combo_file):
            self.assertTrue(os.path.isfile(path), path)


class TestGenerators(BruteforcePluginTestCase):
    def test_user_password_combinations(self):
        generator = self.plugin()._create_user_pass_generator(TARGET)

        combinations = list(generator)

        for user in ("root", "bob"):
            for password in ("secret", "1234"):
                self.assertIn((user, password), combinations)

    def test_password_generator_uses_the_passwords_file(self):
        passwords = list(self.plugin()._create_pass_generator(TARGET))

        self.assertEqual(passwords[:2], ["secret", "1234"])
        self.assertIn("www.example.com", passwords)

    def test_leet_passwords_are_generated_when_enabled(self):
        plugin = self.plugin()
        plugin._l337_p4sswd = True

        passwords = list(plugin._create_pass_generator(TARGET))

        self.assertIn("s3cr3t", passwords)


class TestBruteforceWrapper(BruteforcePluginTestCase):
    def test_audit_is_called_with_a_copy_and_a_debugging_id(self):
        plugin = self.plugin()
        freq = FuzzableRequest(TARGET)

        plugin.bruteforce_wrapper(freq)

        audited, debugging_id = plugin.audited[0]
        self.assertIsNot(audited, freq)
        self.assertEqual(audited.get_uri(), freq.get_uri())
        self.assertRegex(debugging_id, r"^[a-zA-Z0-9]{8}$")

    def test_new_findings_are_returned_as_requests(self):
        plugin = self.plugin()

        found = plugin.bruteforce_wrapper(FuzzableRequest(TARGET))

        self.assertEqual([f.get_uri() for f in found], [TARGET])

    def test_findings_are_only_returned_once(self):
        plugin = self.plugin()
        plugin.bruteforce_wrapper(FuzzableRequest(TARGET))

        found = plugin.bruteforce_wrapper(FuzzableRequest(TARGET))

        self.assertEqual(found, [])


class TestBruteforce(BruteforcePluginTestCase):
    def test_every_combination_is_sent_to_the_workers(self):
        plugin = self.plugin()
        pool = Pool(2, worker_names="BruteforceTestWorker")
        self.addCleanup(pool.terminate_join)
        plugin.set_worker_pool(pool)
        combinations = [("root", "secret"), ("bob", "1234"), ("bob", "secret")]

        plugin._bruteforce("http://www.example.com/login", combinations, "did-1")

        self.assertCountEqual(
            plugin.tried,
            [("http://www.example.com/login", c, "did-1") for c in combinations],
        )


class TestPasswordReport(unittest.TestCase):
    def test_password_is_reported_as_is_by_default(self):
        self.assertEqual(
            BruteforcePlugin()._get_password_for_report("secret"), "secret"
        )

    def test_password_can_be_masked(self):
        plugin = BruteforcePlugin()
        plugin._mask_password_in_report = True

        reported = plugin._get_password_for_report("secret")

        self.assertNotIn("secret", reported)
        self.assertIn("*", reported)


class TestOptions(BruteforcePluginTestCase):
    def test_options_describe_the_current_configuration(self):
        options = self.plugin().get_options()

        values = {option.get_name(): option.get_value() for option in options}
        self.assertEqual(values["users_file"], self.users_file)
        self.assertEqual(values["passwd_file"], self.passwords_file)
        self.assertFalse(values["use_emails"])
        self.assertTrue(values["stop_on_first"])
        self.assertEqual(values["combo_separator"], ":")
        self.assertEqual(values["profiling_number"], 50)
        self.assertEqual(len(values), 12)

    def test_options_round_trip(self):
        source = self.plugin()
        source._stop_on_first = False
        source._use_profiling = True
        source._profiling_number = 7
        source._combo_separator = "|"
        source._mask_password_in_report = True
        target = BruteforcePlugin()

        target.set_options(source.get_options())

        self.assertEqual(target._users_file, self.users_file)
        self.assertEqual(target._passwd_file, self.passwords_file)
        self.assertFalse(target._stop_on_first)
        self.assertFalse(target._pass_eq_user)
        self.assertFalse(target._l337_p4sswd)
        self.assertFalse(target._use_emails)
        self.assertFalse(target._use_SVN_users)
        self.assertTrue(target._use_profiling)
        self.assertEqual(target._profiling_number, 7)
        self.assertEqual(target._combo_separator, "|")
        self.assertTrue(target._mask_password_in_report)
