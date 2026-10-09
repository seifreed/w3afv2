"""
test_audit_plugin_metadata.py

Copyright 2026 w3af contributors

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

import unittest

from w3af.core.controllers.w3af_core import w3afCore


class TestAuditPluginMetadata(unittest.TestCase):

    def setUp(self):
        self.w3afcore = w3afCore()
        self.addCleanup(self.w3afcore.quit)

    def audit_plugins(self):
        plugins = self.w3afcore.plugins
        for name in plugins.get_plugin_list("audit"):
            yield plugins.get_plugin_inst("audit", name)

    def test_every_audit_plugin_describes_itself(self):
        for plugin in self.audit_plugins():
            with self.subTest(plugin=plugin.get_name()):
                self.assertGreater(len(plugin.get_long_desc()), 50)
                self.assertTrue(plugin.get_desc())

    def test_every_audit_plugin_accepts_its_own_options(self):
        for plugin in self.audit_plugins():
            with self.subTest(plugin=plugin.get_name()):
                options = plugin.get_options()
                plugin.set_options(options)

                self.assertEqual(
                    [o.get_value_str() for o in options],
                    [o.get_value_str() for o in plugin.get_options()],
                )
