"""Read-only discovery of the plugins available to w3af."""

import os
import sys
from importlib import import_module
from typing import ClassVar

from w3af import ROOT_PATH
from w3af.core.controllers.misc.factory import factory
from w3af.core.controllers.misc.get_file_list import get_file_list
from w3af.core.exceptions import BaseFrameworkException


class PluginCatalog:
    """Expose plugin metadata without requiring a scan or output services."""

    SUPPORT_MODULES: ClassVar[dict[str, set[str]]] = {
        "output": {"xml_filters", "xml_models", "xml_nodes"}
    }

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
        plugin_names = get_file_list(os.path.join(ROOT_PATH, "plugins", plugin_type))
        return [
            plugin_name
            for plugin_name in plugin_names
            if plugin_name not in self.SUPPORT_MODULES.get(plugin_type, set())
        ]

    def get_quick_instance(self, plugin_type, plugin_name, db):
        module_name = f"w3af.plugins.{plugin_type}.{plugin_name}"
        plugin_module = import_module(module_name)
        plugin_class = getattr(plugin_module, plugin_name)

        if getattr(plugin_class, "uses_database", False):
            return factory(module_name, db)

        return factory(module_name)
