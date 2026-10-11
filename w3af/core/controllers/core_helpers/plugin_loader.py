"""Load and instantiate plugin classes from the plugin package."""

from importlib import import_module

from w3af.core.controllers.misc.factory import factory


def create_plugin_instance(plugin_type, plugin_name, db=None):
    """Instantiate a plugin with its optional database dependency."""
    module_name = f"w3af.plugins.{plugin_type}.{plugin_name}"
    plugin_module = import_module(module_name)
    plugin_class = getattr(plugin_module, plugin_name, None)

    if getattr(plugin_class, "uses_database", False):
        return factory(module_name, db)
    return factory(module_name)
