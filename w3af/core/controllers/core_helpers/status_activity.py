"""Track the plugin activity exposed by the scan status."""


class StatusActivity:
    """Store the latest plugin and request for each scan phase."""

    def __init__(self):
        self._running_plugin = {}
        self._latest_plugin_type = None
        self._latest_plugin_name = None
        self._current_fuzzable_request = {}

    def clear(self):
        """Remove activity left over from a completed scan."""
        self._running_plugin.clear()
        self._current_fuzzable_request.clear()

    def set_running_plugin(self, plugin_type, plugin_name):
        """Record the plugin currently running for a phase."""
        self._running_plugin[plugin_type] = plugin_name
        self._latest_plugin_type = plugin_type
        self._latest_plugin_name = plugin_name

    def get_running_plugin(self, plugin_type):
        """Return the plugin currently running for a phase, if any."""
        return self._running_plugin.get(plugin_type)

    def latest_running_plugin(self):
        """Return the last plugin reported as running."""
        return self._latest_plugin_type, self._latest_plugin_name

    def set_current_fuzzable_request(self, plugin_type, fuzzable_request):
        """Record the request currently handled by a phase."""
        self._current_fuzzable_request[plugin_type] = fuzzable_request

    def get_current_fuzzable_request(self, plugin_type):
        """Return the request currently handled by a phase, if any."""
        return self._current_fuzzable_request.get(plugin_type)
