"""Build the concrete urllib handler chain from opener configuration."""

from dataclasses import dataclass

from w3af.core.data.url.director import CustomOpenerDirector, build_opener
from w3af.core.data.url.handlers.blacklist import BlacklistHandler
from w3af.core.data.url.handlers.cache import CacheHandler
from w3af.core.data.url.handlers.cookie_handler import CookieHandler
from w3af.core.data.url.handlers.errors import ErrorHandler, NoOpErrorHandler
from w3af.core.data.url.handlers.gzip_handler import HTTPGzipProcessor
from w3af.core.data.url.handlers.http_log import HTTPLogHandler
from w3af.core.data.url.handlers.keepalive import HTTPHandler, HTTPSHandler
from w3af.core.data.url.handlers.mangle import MangleHandler
from w3af.core.data.url.handlers.normalize import NormalizeHandler
from w3af.core.data.url.handlers.redirect import HTTP30XHandler
from w3af.core.data.url.handlers.url_parameter import URLParameterHandler


@dataclass
class BuiltOpeners:
    """Resources created together with the custom urllib opener."""

    uri_opener: CustomOpenerDirector
    http_handler: HTTPHandler
    https_handler: HTTPSHandler
    cache_handler: CacheHandler


class OpenerBuilder:
    """Compose the handler chain required by the HTTP runtime."""

    def __init__(
        self,
        configuration,
        http_log_callback,
        proxy_url,
        resolver,
        proxy_handler,
        basic_auth_handler,
        ntlm_auth_handler,
        cookie_handler: CookieHandler,
        mangle_plugins,
        url_parameter_handler: URLParameterHandler | None,
        ignore_session_cookies: bool,
    ):
        self._configuration = configuration
        self._http_log_callback = http_log_callback
        self._proxy_url = proxy_url
        self._resolver = resolver
        self._proxy_handler = proxy_handler
        self._basic_auth_handler = basic_auth_handler
        self._ntlm_auth_handler = ntlm_auth_handler
        self._cookie_handler = cookie_handler
        self._mangle_plugins = mangle_plugins
        self._url_parameter_handler = url_parameter_handler
        self._ignore_session_cookies = ignore_session_cookies

    def build(self) -> BuiltOpeners:
        http_handler = HTTPHandler(self._configuration, self._resolver)
        https_handler = HTTPSHandler(
            self._proxy_url, self._configuration, self._resolver
        )
        cache_handler = CacheHandler()
        handlers = self._build_handlers(
            http_handler,
            https_handler,
            cache_handler,
        )

        if self._ignore_session_cookies:
            handlers.remove(self._cookie_handler)

        uri_opener = build_opener(CustomOpenerDirector, handlers)
        uri_opener.addheaders = [("Accept", "*/*")]

        return BuiltOpeners(
            uri_opener=uri_opener,
            http_handler=http_handler,
            https_handler=https_handler,
            cache_handler=cache_handler,
        )

    def _build_handlers(self, http_handler, https_handler, cache_handler):
        return [
            handler
            for handler in [
                self._proxy_handler,
                self._basic_auth_handler,
                self._ntlm_auth_handler,
                self._cookie_handler,
                NormalizeHandler,
                http_handler,
                https_handler,
                (
                    HTTPLogHandler(self._http_log_callback)
                    if self._http_log_callback is not None
                    else None
                ),
                HTTP30XHandler,
                BlacklistHandler(self._configuration),
                MangleHandler(self._mangle_plugins),
                HTTPGzipProcessor,
                self._url_parameter_handler,
                cache_handler,
                ErrorHandler,
                NoOpErrorHandler,
            ]
            if handler
        ]
