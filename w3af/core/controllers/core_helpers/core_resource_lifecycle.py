"""Own the resources that must be released with a scan core."""


class CoreResourceLifecycle:
    """Release core-owned resources in their dependency-safe order."""

    def __init__(
        self, output_manager, dns_cache, parser_cache, database, worker_pool_manager
    ):
        self._output_manager = output_manager
        self._dns_cache = dns_cache
        self._parser_cache = parser_cache
        self._database = database
        self._worker_pool_manager = worker_pool_manager
        self._verification_service = None
        self._stopped = False

    def set_verification_service(self, verification_service):
        """Bind the service created after the URL opener is available."""
        self._verification_service = verification_service

    def stop(self):
        """Release every owned resource once."""
        if self._stopped:
            return

        self._stopped = True
        self._worker_pool_manager.terminate()
        if self._verification_service is not None:
            self._verification_service.shutdown()
        self._parser_cache.clear()
        self._dns_cache.clear()
        self._output_manager.stop()
        if self._database is not None:
            self._database.close()
