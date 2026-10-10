import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from w3af.core.controllers.dependency_check.helper_script import (
    SCRIPT_NAME,
    generate_helper_script,
    generate_pip_install_git,
    generate_pip_install_non_git,
)
from w3af.core.controllers.dependency_check.pip_dependency import PIPDependency

PLAIN = PIPDependency("a", "pkg-a", "1.0")
OTHER = PIPDependency("b", "pkg-b", "2.5")
GIT = PIPDependency("g", "pkg-g", "abc", git_src="git+https://example.invalid/g@abc")


class TestPipInstallCommands(unittest.TestCase):
    def test_non_git_in_virtualenv_does_not_use_sudo(self):
        cmd = generate_pip_install_non_git("python -m pip", [PLAIN, OTHER], True)
        self.assertEqual(cmd, "python -m pip install pkg-a==1.0 pkg-b==2.5")

    def test_non_git_outside_virtualenv_uses_sudo(self):
        cmd = generate_pip_install_non_git("pip", [PLAIN], False)
        self.assertEqual(cmd, "sudo pip install pkg-a==1.0")

    def test_git_in_virtualenv_does_not_use_sudo(self):
        cmd = generate_pip_install_git("pip", GIT.git_src, True)
        self.assertEqual(
            cmd, "pip install --ignore-installed git+https://example.invalid/g@abc"
        )

    def test_git_outside_virtualenv_uses_sudo(self):
        cmd = generate_pip_install_git("pip", GIT.git_src, False)
        self.assertEqual(
            cmd,
            "sudo pip install --ignore-installed git+https://example.invalid/g@abc",
        )


class TestGenerateHelperScript(unittest.TestCase):
    def generate(self, *args):
        with tempfile.TemporaryDirectory() as directory:
            path = generate_helper_script(directory, *args)
            self.assertEqual(path, os.path.join(directory, SCRIPT_NAME))
            return Path(path).read_text(), os.stat(path).st_mode

    def test_script_with_everything_missing(self):
        script, _ = self.generate(
            "sudo apt install", ["libx", "liby"], "pip", [PLAIN, GIT], ["npm i"], True
        )

        self.assertEqual(
            script,
            "#!/bin/bash\n"
            "sudo apt install libx liby\n"
            "\n"
            "# Run without sudo to install inside venv\n"
            "pip install pkg-a==1.0\n"
            "pip install --ignore-installed git+https://example.invalid/g@abc\n"
            "npm i\n",
        )

    def test_script_outside_virtualenv_uses_sudo_and_has_no_comment(self):
        script, _ = self.generate("", [], "pip", [PLAIN], [], False)

        self.assertEqual(script, "#!/bin/bash\n\nsudo pip install pkg-a==1.0\n")

    def test_script_without_python_modules_only_has_other_commands(self):
        script, _ = self.generate("pm", ["libx"], "pip", [], ["npm i"], True)

        self.assertEqual(script, "#!/bin/bash\npm libx\nnpm i\n")

    @unittest.skipIf(sys.platform == "win32", "POSIX permission bits")
    def test_script_is_executable_by_its_owner_only(self):
        _, mode = self.generate("pm", [], "pip", [], [], True)

        self.assertEqual(stat.S_IMODE(mode), 0o700)
