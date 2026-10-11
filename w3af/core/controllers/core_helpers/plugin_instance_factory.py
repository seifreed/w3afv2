"""Build and configure runtime plugin instances."""

from typing import Protocol

from w3af.core.controllers.core_helpers.plugin_loader import create_plugin_instance


class PluginCoreContext(Protocol):
    """Core services required to initialize a plugin instance."""

    @property
    def database(self) -> object: ...

    @property
    def uri_opener(self) -> object: ...

    @property
    def worker_pool(self) -> object: ...

    @property
    def configuration(self) -> object: ...

    @property
    def knowledge_base(self) -> object: ...

    @property
    def parser_cache(self) -> object: ...

    @property
    def id_generator(self) -> object: ...


class PluginInstanceFactory:
    """Create plugins with the runtime dependencies supplied by the core."""

    def __init__(self, plugin_context: PluginCoreContext, output):
        self._plugin_context = plugin_context
        self._output = output

    def create(self, plugin_type, plugin_name, custom_options=None):
        plugin_instance = create_plugin_instance(
            plugin_type, plugin_name, self._plugin_context.database
        )
        plugin_instance.set_url_opener(self._plugin_context.uri_opener)
        plugin_instance.set_worker_pool(self._plugin_context.worker_pool)
        plugin_instance.set_w3af_core(self._plugin_context)
        plugin_instance.set_configuration(self._plugin_context.configuration)
        plugin_instance.set_knowledge_base(self._plugin_context.knowledge_base)
        plugin_instance.set_output(self._output)
        plugin_instance.set_parser_cache(self._plugin_context.parser_cache)
        plugin_instance.set_id_generator(self._plugin_context.id_generator)

        if custom_options is not None:
            plugin_instance.set_options(custom_options)

        return plugin_instance
