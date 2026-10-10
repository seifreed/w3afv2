import unittest

from w3af.core.controllers.exceptions import (
    ExploitFailedException,
    NoVulnerabilityFoundException,
)
from w3af.core.controllers.plugins.attack_plugin import AttackPlugin
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.data.constants import severity
from w3af.core.data.kb.knowledge_base import kb
from w3af.core.data.kb.shell import Shell
from w3af.core.data.kb.vuln import Vuln
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.exceptions import (
    ScanMustStopByUnknownReasonExc,
    ScanMustStopByUserRequest,
    ScanMustStopException,
)

LOCATION = "unit_test_vuln"
OTHER_LOCATION = "other_unit_test_vuln"


class unit_attack(AttackPlugin):
    """
    Attack plugin that exploits every vulnerability stored in the kb, the
    outcome of each exploitation is defined by the `outcomes` list.
    """

    def __init__(self, outcomes=None, generate_only_one=False):
        AttackPlugin.__init__(self)
        self.set_knowledge_base(kb)
        self.outcomes = outcomes or []
        self._generate_only_one = generate_only_one
        self.exploited = []

    def _generate_shell(self, vuln):
        self.exploited.append(vuln)
        outcome = self.outcomes[len(self.exploited) - 1]

        if isinstance(outcome, Exception):
            raise outcome

        return outcome

    def get_kb_location(self):
        return [LOCATION, OTHER_LOCATION]


def vuln_for(path, plugin_name="unit_audit", response_ids=()):
    url = URL(f"http://127.0.0.1/{path}")
    return Vuln.from_fr(
        "SQL injection",
        "Unit test vulnerability",
        severity.HIGH,
        list(response_ids),
        plugin_name,
        FuzzableRequest(url),
    )


class AttackPluginTestCase(unittest.TestCase):
    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)


class TestNotImplementedMethods(unittest.TestCase):
    def test_required_methods(self):
        plugin = AttackPlugin()
        vuln = vuln_for("a")

        self.assertRaises(NotImplementedError, plugin._generate_shell, vuln)
        self.assertRaises(NotImplementedError, plugin.get_attack_type)
        self.assertRaises(NotImplementedError, plugin.get_root_probability)
        self.assertRaises(NotImplementedError, plugin.get_kb_location)


class TestPluginInformation(unittest.TestCase):
    def test_type_is_attack(self):
        self.assertEqual(unit_attack().get_type(), "attack")

    def test_attack_plugins_have_no_plugin_dependencies(self):
        self.assertEqual(unit_attack().get_plugin_deps(), [])


class TestCanExploit(AttackPluginTestCase):
    def test_no_vulnerabilities_in_the_kb(self):
        self.assertFalse(unit_attack().can_exploit())

    def test_vulnerabilities_from_any_kb_location(self):
        kb.append(OTHER_LOCATION, OTHER_LOCATION, vuln_for("a"))

        self.assertTrue(unit_attack().can_exploit())

    def test_exploitable_vulns_are_collected_from_every_location(self):
        first, second = vuln_for("a"), vuln_for("b")
        kb.append(LOCATION, LOCATION, first)
        kb.append(OTHER_LOCATION, OTHER_LOCATION, second)

        self.assertEqual(unit_attack().get_exploitable_vulns(), [first, second])

    def test_exploit_a_specific_vulnerability_id(self):
        vuln = Vuln.from_fr(
            "SQL injection",
            "Unit test vulnerability",
            severity.HIGH,
            [4242],
            "p",
            FuzzableRequest(URL("http://x/")),
        )
        kb.append(LOCATION, LOCATION, vuln)

        self.assertTrue(unit_attack().can_exploit([4242]))
        self.assertFalse(unit_attack().can_exploit([1]))

    def test_vulnerability_ids_must_be_a_list_of_integers(self):
        for invalid in (4242, "4242", (1,), ["1"], [1, "2"]):
            with self.subTest(invalid=invalid):
                self.assertRaises(TypeError, unit_attack().can_exploit, invalid)


class unit_shell(Shell):
    def identify_os(self):
        self._rOS = "unit test operating system"

    def get_name(self):
        return "unit_shell"

    def __reduce__(self):
        return self.__class__, (self._vuln, None, None)


def shell_for(vuln):
    return unit_shell(vuln, None, None)


class TestExploit(AttackPluginTestCase):
    def test_nothing_to_exploit(self):
        with self.assertRaises(NoVulnerabilityFoundException) as context:
            unit_attack().exploit()

        self.assertIn(
            f"No {LOCATION} or {OTHER_LOCATION} vulnerabilities", str(context.exception)
        )

    def test_shells_are_stored_in_the_kb_and_returned(self):
        first, second = vuln_for("a"), vuln_for("b")
        kb.append(LOCATION, LOCATION, first)
        kb.append(OTHER_LOCATION, OTHER_LOCATION, second)
        shell = shell_for(first)
        recorder = start_recording_output()

        shells = unit_attack([shell, None]).exploit()

        self.assertEqual(shells, [shell])
        self.assertIs(shell.get_knowledge_base(), kb)
        self.assertEqual(kb.get("unit_attack", "shell"), [shell])
        self.assertTrue(
            any(
                "Vulnerability successfully exploited" in m
                for m in recorder.messages_of("console")
            )
        )

    def test_all_the_shells_are_returned_by_default(self):
        first, second = vuln_for("a"), vuln_for("b")
        kb.append(LOCATION, LOCATION, first)
        kb.append(LOCATION, LOCATION, second)
        expected = [shell_for(first), shell_for(second)]

        shells = unit_attack(expected).exploit()

        self.assertEqual(shells, expected)

    def test_stops_after_the_first_shell_when_only_one_is_needed(self):
        first, second = vuln_for("a"), vuln_for("b")
        kb.append(LOCATION, LOCATION, first)
        kb.append(LOCATION, LOCATION, second)
        shell = shell_for(first)
        plugin = unit_attack([shell, shell_for(second)], generate_only_one=True)

        shells = plugin.exploit()

        self.assertEqual(shells, [shell])
        self.assertEqual(len(plugin.exploited), 1)

    def test_only_the_requested_vulnerability_is_exploited(self):
        first = vuln_for("a", response_ids=[1])
        second = vuln_for("b", response_ids=[2])
        kb.append(LOCATION, LOCATION, first)
        kb.append(LOCATION, LOCATION, second)
        shell = shell_for(second)
        plugin = unit_attack([shell])

        shells = plugin.exploit([2])

        self.assertEqual(shells, [shell])
        self.assertEqual(plugin.exploited, [second])

    def test_vulnerability_without_url_is_skipped(self):
        vuln = Vuln("SQL injection", "Unit test vulnerability", severity.HIGH, [], "p")
        kb.append(LOCATION, LOCATION, vuln)
        plugin = unit_attack()
        recorder = start_recording_output()

        self.assertEqual(plugin.exploit(), [])

        self.assertEqual(plugin.exploited, [])
        self.assertTrue(
            any("doesn't have an URL" in m for m in recorder.messages_of("debug"))
        )

    def test_vulnerability_without_http_method_is_skipped(self):
        vuln = vuln_for("a")
        vuln.set_method(None)
        kb.append(LOCATION, LOCATION, vuln)
        plugin = unit_attack()
        recorder = start_recording_output()

        self.assertEqual(plugin.exploit(), [])

        self.assertEqual(plugin.exploited, [])
        self.assertTrue(
            any(
                "doesn't have an HTTP method" in m
                for m in recorder.messages_of("debug")
            )
        )

    def test_exploitation_errors_are_reported_as_failed_exploits(self):
        errors = (
            HTTPRequestException("http failure"),
            ScanMustStopException("stop"),
            ScanMustStopByUnknownReasonExc("unknown"),
            ScanMustStopByUserRequest("user"),
        )

        for error in errors:
            with self.subTest(error=type(error).__name__):
                kb.cleanup()
                kb.append(LOCATION, LOCATION, vuln_for("a"))

                with self.assertRaises(ExploitFailedException) as context:
                    unit_attack([error]).exploit()

                self.assertIn(
                    "The exploitation failed due to HTTP exception",
                    str(context.exception),
                )
