"""Build and configure runtime plugin instances."""

from w3af.core.controllers.misc.factory import factory
from w3af.core.data.db.dbms import database_context


class PluginInstanceFactory:
    """Create plugins with the runtime dependencies supplied by the core."""

    def __init__(self, w3af_core, output):
        self._w3af_core = w3af_core
        self._output = output

    def create(self, plugin_type, plugin_name, custom_options=None):
        with database_context(self._w3af_core.database):
            plugin_instance = factory(f"w3af.plugins.{plugin_type}.{plugin_name}")
        plugin_instance.set_url_opener(self._w3af_core.uri_opener)
        plugin_instance.set_worker_pool(self._w3af_core.worker_pool)
        plugin_instance.set_w3af_core(self._w3af_core)
        plugin_instance.set_configuration(self._w3af_core.configuration)
        plugin_instance.set_knowledge_base(self._w3af_core.knowledge_base)
        plugin_instance.set_output(self._output)
        plugin_instance.set_parser_cache(self._w3af_core.parser_cache)
        plugin_instance.set_id_generator(self._w3af_core.id_generator)

        if custom_options is not None:
            plugin_instance.set_options(custom_options)

        return plugin_instance
