"""
test_architecture_layers.py

Copyright 2024 Andres Riancho

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

# Clean Architecture layering, from the innermost (0) to the outermost (3).
# A module in an inner layer must never import a module in an outer one.
LAYERS = (
    ("w3af.core.data", 0),
    ("w3af.core.controllers", 1),
    ("w3af.plugins", 2),
    ("w3af.core.ui", 3),
)

W3AF_PACKAGE = Path(__file__).resolve().parents[1]
REPO_ROOT = W3AF_PACKAGE.parent


def layer_of(module_name):
    for prefix, index in LAYERS:
        if module_name == prefix or module_name.startswith(prefix + "."):
            return index
    return None


def is_test_module(relative_path):
    return (
        "tests" in relative_path.parts
        or relative_path.name.startswith("test_")
        or relative_path.name == "conftest.py"
    )


def module_name_for(relative_path):
    name = ".".join(relative_path.with_suffix("").parts)
    name = name.removesuffix(".__init__")
    return name


def resolve_import_target(node, package):
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]

    base = package
    if node.level:
        parts = package.split(".")
        parts = parts[: len(parts) - (node.level - 1)]
        base = ".".join(parts + ([node.module] if node.module else []))
    else:
        base = node.module or ""

    if layer_of(base) is not None:
        return [base]
    return [f"{base}.{alias.name}" for alias in node.names]


def collect_violations():
    violations = set()

    for path in sorted(W3AF_PACKAGE.rglob("*.py")):
        relative_path = path.relative_to(REPO_ROOT)
        if is_test_module(relative_path):
            continue

        module_name = module_name_for(relative_path)
        source_layer = layer_of(module_name)
        if source_layer is None:
            continue

        if path.name == "__init__.py":
            package = module_name
        else:
            package = module_name.rsplit(".", 1)[0]

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            for target in resolve_import_target(node, package):
                target_layer = layer_of(target)
                if target_layer is not None and target_layer > source_layer:
                    violations.add((module_name, target))

    return violations


class TestArchitectureLayers(unittest.TestCase):
    def test_no_cross_layer_imports(self):
        violations = collect_violations()

        self.assertEqual(
            violations,
            set(),
            "Clean Architecture layering violations (an inner layer imports an "
            "outer one):\n"
            + "\n".join(
                f"  {module} -> {target}" for module, target in sorted(violations)
            ),
        )


if __name__ == "__main__":
    unittest.main()
