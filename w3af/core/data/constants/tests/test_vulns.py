"""
test_vulns.py

Copyright 2006 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""

import ast
import unittest
from pathlib import Path

from vulndb import DBVuln

from w3af.core.data.constants.vulns import VULNS


class TestVulnsConstants(unittest.TestCase):

    def test_vulnerability_names_unique(self):
        source_path = Path(__file__).resolve().parents[1] / "vulns.py"
        module = ast.parse(source_path.read_text(encoding="utf-8"))
        registry = next(
            node.value
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "VULNS"
                for target in node.targets
            )
        )
        assert isinstance(registry, ast.Dict)
        names = [key.value for key in registry.keys if isinstance(key, ast.Constant)]

        self.assertEqual(len(names), len(set(names)))

    def get_plugin_sources(self):
        package_root = Path(__file__).resolve().parents[3]
        source_roots = (
            (package_root / "plugins", {"test", "tests", "payloads"}),
            (package_root / "core" / "data" / "kb" / "vuln_templates", {"tests"}),
        )

        for source_root, excluded_directories in source_roots:
            for path in source_root.rglob("*.py"):
                relative_parts = path.relative_to(source_root).parts
                if path.name.startswith("test_"):
                    continue
                if excluded_directories.intersection(relative_parts[:-1]):
                    continue
                if relative_parts[:3] == ("attack", "db", "sqlmap"):
                    continue
                yield path

    def test_literal_vulnerability_names_are_registered(self):
        unregistered = set()

        for path in self.get_plugin_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                if isinstance(node.func, ast.Name):
                    function_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    function_name = node.func.attr
                else:
                    continue

                if function_name != "Vuln":
                    continue

                name = (
                    node.args[0]
                    if node.args
                    else next(
                        (
                            keyword.value
                            for keyword in node.keywords
                            if keyword.arg == "name"
                        ),
                        None,
                    )
                )
                if (
                    isinstance(name, ast.Constant)
                    and isinstance(name.value, str)
                    and name.value not in VULNS
                ):
                    unregistered.add((name.value, str(path), node.lineno))

        self.assertEqual([], sorted(unregistered))

    def test_vulns_dict_points_to_existing_vulndb_data_id(self):
        invalid = []
        for vuln_name, _id in VULNS.items():
            if _id is None:
                continue

            if not DBVuln.is_valid_id(_id, language=DBVuln.DEFAULT_LANG):
                invalid.append((vuln_name, _id))

        self.assertEqual(invalid, [])
