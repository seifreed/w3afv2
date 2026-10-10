import unittest

from w3af.core.controllers.dependency_check.pip_dependency import PIPDependency


class TestPIPDependency(unittest.TestCase):
    def test_plain_dependency_is_not_git(self):
        dependency = PIPDependency("yaml", "PyYAML", "6.0")

        self.assertFalse(dependency.is_git)
        self.assertIsNone(dependency.git_src)
        self.assertIsNone(dependency.tgz_src)

    def test_git_source_marks_dependency_as_git(self):
        dependency = PIPDependency(
            "m", "m", "abc", git_src="git+https://x/m@abc", tgz_src="https://x/m.tgz"
        )

        self.assertTrue(dependency.is_git)
        self.assertEqual(dependency.git_src, "git+https://x/m@abc")
        self.assertEqual(dependency.tgz_src, "https://x/m.tgz")

    def test_tgz_source_is_ignored_without_git_source(self):
        self.assertIsNone(PIPDependency("m", "m", "1", tgz_src="x").tgz_src)

    def test_equality_compares_every_field(self):
        base = PIPDependency("yaml", "PyYAML", "6.0", git_src="g", tgz_src="t")

        self.assertEqual(base, PIPDependency("yaml", "PyYAML", "6.0", "g", "t"))
        self.assertNotEqual(base, PIPDependency("yml", "PyYAML", "6.0", "g", "t"))
        self.assertNotEqual(base, PIPDependency("yaml", "Other", "6.0", "g", "t"))
        self.assertNotEqual(base, PIPDependency("yaml", "PyYAML", "6.1", "g", "t"))
        self.assertNotEqual(base, PIPDependency("yaml", "PyYAML", "6.0", "h", "t"))
        self.assertNotEqual(base, PIPDependency("yaml", "PyYAML", "6.0", "g", "u"))
        self.assertNotEqual(base, PIPDependency("yaml", "PyYAML", "6.0"))

    def test_repr_shows_package_and_version(self):
        self.assertEqual(
            repr(PIPDependency("yaml", "PyYAML", "6.0")),
            "<PIPDependency (PyYAML|6.0)>",
        )
