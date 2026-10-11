"""Own and configure the output plugin instances used by a manager."""

import logging
import os
from collections.abc import Callable
from importlib import import_module
from typing import Any

from w3af import ROOT_PATH
from w3af.core.controllers.misc.factory import factory
from w3af.core.controllers.plugins.output_plugin import OutputPlugin
from w3af.core.controllers.plugins.plugin_runtime_context import (
    PluginRuntimeContext,
)
from w3af.core.data.db.dbms import SQLiteDBMS, create_temp_db_instance

LOGGER = logging.getLogger(__name__)


class OutputPluginRegistry:
    """Manage output plugin ownership independently from queue processing."""

    def __init__(
        self,
        get_plugin_runtime_context: Callable[[], PluginRuntimeContext | None],
        output=None,
    ) -> None:
        self._get_plugin_runtime_context = get_plugin_runtime_context
        self._output = output
        self._knowledge_base = None
        self._instances: list[OutputPlugin] = []
        self._plugin_names: list[str] = []
        self._plugin_options: dict[str, Any] = {}
        self._standalone_database: SQLiteDBMS | None = None

    def set_output(self, output) -> None:
        self._output = output

    def set_knowledge_base(self, knowledge_base) -> None:
        self._knowledge_base = knowledge_base

    def get_instances(self) -> list[OutputPlugin]:
        return list(self._instances)

    def add_instance(self, output_plugin: OutputPlugin) -> None:
        self._instances.append(output_plugin)

    def remove_instance(self, output_plugin: OutputPlugin) -> None:
        self._instances.remove(output_plugin)

    def take_instances(self) -> list[OutputPlugin]:
        instances = self._instances
        self._instances = []
        return instances

    def end_instances(self, output_plugins: list[OutputPlugin]) -> None:
        """End every supplied plugin and preserve the first failure."""
        first_exception = None
        for output_plugin in output_plugins:
            try:
                output_plugin.end()
            except Exception as exception:
                LOGGER.debug("Output plugin end() failed", exc_info=True)
                if first_exception is None:
                    first_exception = exception

        if first_exception is not None:
            raise first_exception

    def set_plugins(self, output_plugins) -> None:
        previous_plugins = self.take_instances()
        try:
            self.end_instances(previous_plugins)
        finally:
            self.close_standalone_database()

        self._plugin_names = list(output_plugins)
        for plugin_name in self._plugin_names:
            self._add_plugin(plugin_name)

    def get_plugins(self):
        return list(self._plugin_names)

    def set_plugin_options(self, plugin_name, plugin_options) -> None:
        self._plugin_options[plugin_name] = plugin_options

    def close_standalone_database(self) -> None:
        database = self._standalone_database
        if database is None:
            return

        if not database.sql_executor.get_received_poison_pill():
            database.close()
        self._standalone_database = None

    def has_standalone_database(self) -> bool:
        return self._standalone_database is not None

    def _get_standalone_database(self):
        if self._standalone_database is None:
            self._standalone_database = create_temp_db_instance()
        return self._standalone_database

    def _add_plugin(self, output_plugin_name) -> None:
        if output_plugin_name == "all":
            file_list = os.listdir(os.path.join(ROOT_PATH, "plugins", "output"))
            for filename in file_list:
                plugin_name, extension = os.path.splitext(filename)
                if extension != ".py" or plugin_name == "__init__":
                    continue

                module = import_module(f"w3af.plugins.output.{plugin_name}")
                plugin_class = getattr(module, plugin_name, None)
                if isinstance(plugin_class, type) and issubclass(
                    plugin_class, OutputPlugin
                ):
                    self.add_instance(self._get_plugin_instance(plugin_name))
            return

        self.add_instance(self._get_plugin_instance(output_plugin_name))

    def _get_plugin_instance(self, plugin_name):
        runtime_context = self._get_plugin_runtime_context()
        module = import_module(f"w3af.plugins.output.{plugin_name}")
        plugin_class = getattr(module, plugin_name)
        database = self._get_plugin_database(plugin_class, runtime_context)
        plugin = (
            factory(f"w3af.plugins.output.{plugin_name}", database)
            if database is not None
            else factory(f"w3af.plugins.output.{plugin_name}")
        )

        plugin.set_runtime_context(runtime_context)
        plugin.set_output(self._output)
        if runtime_context is not None:
            plugin.set_configuration(runtime_context.configuration)
        if self._knowledge_base is not None:
            plugin.set_knowledge_base(self._knowledge_base)
        if plugin_name in self._plugin_options:
            plugin.set_options(self._plugin_options[plugin_name])

        return plugin

    def _get_plugin_database(self, plugin_class, runtime_context):
        if not getattr(plugin_class, "uses_database", False):
            return None
        if runtime_context is not None:
            return runtime_context.database
        return self._get_standalone_database()
