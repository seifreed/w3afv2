import io
import sys
import unittest
from contextlib import redirect_stdout

from w3af.core.controllers.dependency_check.external.retirejs import (
    retirejs_is_installed,
)
from w3af.core.controllers.dependency_check.platforms.base_platform import (
    RETIREJS_INSTALL_COMMANDS,
    Platform,
)
from w3af.core.controllers.dependency_check.platforms.current_platform import (
    KNOWN_PLATFORMS,
    get_current_platform,
)
from w3af.core.controllers.dependency_check.platforms.default import DefaultPlatform
from w3af.core.controllers.dependency_check.platforms.fedora import (
    Fedora,
    classify_rpm_output,
)
from w3af.core.controllers.dependency_check.platforms.mac import (
    MACPORTS_PREFIX,
    TWO_PYTHON_MSG,
    MacOSX,
    classify_port_output,
    two_python_warning,
)

RPM_INSTALLED = "libxml2-devel-2.12.6-1.fc40.x86_64\n"
RPM_NOT_INSTALLED = "package libxml2-devel is not installed\n"
PORT_INSTALLED = (
    "The following ports are currently installed:\n" "  autoconf @2.72_0 (active)\n"
)
PORT_NOT_INSTALLED = "None of the specified ports are installed.\n"


class TestBasePlatform(unittest.TestCase):
    def test_abstract_queries_must_be_implemented(self):
        with self.assertRaises(NotImplementedError):
            Platform.is_current_platform()

        with self.assertRaises(NotImplementedError):
            Platform.os_package_is_installed("libfoo")

    def test_default_after_hook_does_nothing(self):
        output = io.StringIO()

        with redirect_stdout(output):
            self.assertIsNone(Platform.after_hook())

        self.assertEqual(output.getvalue(), "")

    def test_external_commands_depend_on_retirejs_installation(self):
        expected = [] if retirejs_is_installed() else RETIREJS_INSTALL_COMMANDS

        self.assertEqual(Platform.get_missing_external_commands(), expected)

    def test_no_external_commands_are_missing_when_retirejs_is_installed(self):
        program = "import sys; print('2.0.3')"
        retirejs = (sys.executable, "-c", program)

        self.assertEqual(Platform.get_missing_external_commands(retirejs), [])

    def test_retirejs_install_commands_when_it_is_not_installed(self):
        retirejs = ("retire-is-not-installed-here",)

        self.assertEqual(
            Platform.get_missing_external_commands(retirejs),
            RETIREJS_INSTALL_COMMANDS,
        )

    def test_missing_external_commands_can_be_modified_by_callers(self):
        commands = Platform.get_missing_external_commands()
        commands.append("changed")

        self.assertNotIn("changed", Platform.get_missing_external_commands())


class TestDefaultPlatform(unittest.TestCase):
    def test_is_the_fallback_platform(self):
        self.assertTrue(DefaultPlatform.is_current_platform())

    def test_has_no_operating_system_packages(self):
        self.assertFalse(DefaultPlatform.os_package_is_installed("anything"))


class TestCurrentPlatform(unittest.TestCase):
    def test_the_platform_of_this_system_is_known_or_default(self):
        current = get_current_platform()

        known = [p for p in KNOWN_PLATFORMS if p.is_current_platform()]
        expected = known[0] if known else DefaultPlatform
        self.assertIsInstance(current, expected)


class TestFedora(unittest.TestCase):
    def test_installed_package(self):
        self.assertTrue(classify_rpm_output(RPM_INSTALLED, "libxml2-devel"))

    def test_package_that_is_not_installed(self):
        self.assertFalse(classify_rpm_output(RPM_NOT_INSTALLED, "libxml2-devel"))

    def test_unrelated_output_is_unknown(self):
        self.assertIsNone(classify_rpm_output("error: bad query\n", "libxml2-devel"))

    def test_package_query_runs_the_system_package_manager(self):
        installed = Fedora.os_package_is_installed("w3af-no-such-package")

        self.assertIn(installed, (False, None))

    def test_current_platform_detection_is_a_boolean(self):
        self.assertIsInstance(Fedora.is_current_platform(), bool)

    def test_declares_dnf_as_package_manager(self):
        self.assertEqual(Fedora.PKG_MANAGER_CMD, "sudo dnf install")
        self.assertIn("python3-pip", Fedora.SYSTEM_PACKAGES[1])


class TestMacOSX(unittest.TestCase):
    def test_installed_port(self):
        self.assertTrue(classify_port_output(PORT_INSTALLED, "autoconf"))

    def test_port_that_is_not_installed(self):
        self.assertFalse(classify_port_output(PORT_NOT_INSTALLED, "autoconf"))

    def test_unrelated_output_is_unknown(self):
        self.assertIsNone(classify_port_output("Error: port not found\n", "autoconf"))

    def test_package_query_runs_macports(self):
        installed = MacOSX.os_package_is_installed("w3af-no-such-port")

        self.assertIn(installed, (False, None))

    def test_current_platform_matches_the_interpreter_platform(self):
        self.assertEqual(MacOSX.is_current_platform(), sys.platform == "darwin")

    def test_macports_python_does_not_need_a_warning(self):
        self.assertIsNone(two_python_warning(MACPORTS_PREFIX + "local/bin/python3.14"))

    def test_other_python_gets_the_two_installations_warning(self):
        warning = two_python_warning("/usr/bin/python3")

        self.assertEqual(warning, TWO_PYTHON_MSG % "/usr/bin/python3")
        self.assertIn("sudo port select --set python python314", warning)

    def test_after_hook_warns_about_the_running_interpreter(self):
        output = io.StringIO()

        with redirect_stdout(output):
            MacOSX.after_hook()

        warning = two_python_warning(sys.executable)
        self.assertEqual(output.getvalue(), "" if warning is None else warning + "\n")
