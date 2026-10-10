"""Read-only discovery of the plugins available to w3af."""

import os
import sys

from w3af import ROOT_PATH
from w3af.core.controllers.misc.factory import factory
from w3af.core.controllers.misc.get_file_list import get_file_list
from w3af.core.exceptions import BaseFrameworkException


class PluginCatalog:
    """Expose plugin metadata without requiring a scan or output services."""

    def get_plugin_type_desc(self, plugin_type):
        try:
            __import__(f"w3af.plugins.{plugin_type}")
            plugin_module = sys.modules[f"w3af.plugins.{plugin_type}"]
        except Exception as exception:
            msg = 'Unknown plugin type: "%s".'
            raise BaseFrameworkException(msg % plugin_type) from exception
        return plugin_module.get_long_description()

    def get_plugin_types(self):
        plugin_root = os.path.join(ROOT_PATH, "plugins")
        plugin_types = os.listdir(plugin_root)
        plugin_types = [
            plugin_type
            for plugin_type in plugin_types
            if os.path.isfile(os.path.join(plugin_root, plugin_type, "__init__.py"))
        ]
        return sorted(
            plugin_type
            for plugin_type in plugin_types
            if plugin_type not in {"attack", "tests"}
        )

    def get_plugin_list(self, plugin_type):
        return get_file_list(os.path.join(ROOT_PATH, "plugins", plugin_type))

    def get_quick_instance(self, plugin_type, plugin_name):
        return factory(f"w3af.plugins.{plugin_type}.{plugin_name}")
