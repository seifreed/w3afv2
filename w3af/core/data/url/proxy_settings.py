"""Configure the proxy handler used by the HTTP opener."""

import urllib.request
from collections.abc import Callable

from w3af.core.exceptions import BaseFrameworkException


class ProxySettings:
    """Manage the configured proxy address and handler."""

    def __init__(self, configuration, log_debug: Callable[..., None]) -> None:
        self._configuration = configuration
        self._log_debug = log_debug
        self.proxy_handler: urllib.request.ProxyHandler | None = None

    def set_proxy(self, ip, port) -> None:
        self._log_debug("Called set_proxy(%s, %s)", ip, port)

        if not ip:
            self._configuration.save("proxy_address", "")
            self._configuration.save("proxy_port", port)
            self.proxy_handler = None
            return

        if port > 65535 or port < 1:
            self.proxy_handler = None
            raise BaseFrameworkException("Invalid port number: " + str(port))

        self._configuration.save("proxy_address", ip)
        self._configuration.save("proxy_port", port)
        proxy_url = f"http://{ip}:{port}"
        self.proxy_handler = urllib.request.ProxyHandler({"http": proxy_url})

    def get_proxy(self):
        return (
            self._configuration.get("proxy_address")
            + ":"
            + str(self._configuration.get("proxy_port"))
        )
