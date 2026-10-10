"""Configure limits applied to HTTP requests."""

from w3af.core.exceptions import BaseFrameworkException


class RequestLimitsSettings:
    """Manage timeout, size, retry, and request-rate settings."""

    def __init__(self, configuration) -> None:
        self._configuration = configuration

    def set_configured_timeout(self, timeout) -> None:
        if timeout < 0 or timeout > 30:
            raise BaseFrameworkException(
                "The timeout parameter should be between 0 and 30 seconds."
            )
        self._configuration.save("configured_timeout", timeout)

    def get_configured_timeout(self):
        return self._configuration.get("configured_timeout")

    def set_max_file_size(self, max_file_size) -> None:
        self._configuration.save("max_file_size", max_file_size)

    def set_max_http_retries(self, retry_num) -> None:
        self._configuration.save("max_http_retries", retry_num)

    def set_max_requests_per_second(self, max_requests_per_second) -> None:
        self._configuration.save("max_requests_per_second", max_requests_per_second)

    def get_max_requests_per_second(self):
        return self._configuration.get("max_requests_per_second")

    def get_max_retrys(self):
        return self._configuration.get("max_http_retries")
