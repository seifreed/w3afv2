"""Close every resource owned by a w3af core instance."""

from collections.abc import Callable


class CoreShutdownLifecycle:
    """Run the process-exit cleanup in dependency-safe order."""

    def __init__(
        self,
        stop_scan: Callable[[], None],
        stop_profiling: Callable[[], None],
        end_uri_opener: Callable[[], None],
        clear_dns_cache: Callable[[], None],
        cleanup_fingerprint: Callable[[], None],
        remove_data_logging: Callable[[], None],
        release_resources: Callable[[], None],
        remove_temp_dir: Callable[[], None],
    ) -> None:
        self._stop_scan = stop_scan
        self._stop_profiling = stop_profiling
        self._end_uri_opener = end_uri_opener
        self._clear_dns_cache = clear_dns_cache
        self._cleanup_fingerprint = cleanup_fingerprint
        self._remove_data_logging = remove_data_logging
        self._release_resources = release_resources
        self._remove_temp_dir = remove_temp_dir

    def quit(self) -> None:
        """Stop the scan and release all core-owned resources."""
        self._stop_scan()
        self._stop_profiling()
        self._end_uri_opener()
        self._clear_dns_cache()
        self._cleanup_fingerprint()
        self._remove_data_logging()
        self._release_resources()
        self._remove_temp_dir()
