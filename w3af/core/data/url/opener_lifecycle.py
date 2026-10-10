"""Manage the resources created by the HTTP opener builder."""

from w3af.core.data.url.opener_builder import BuiltOpeners, OpenerBuilder


class OpenerLifecycle:
    """Build, expose, close, and clear the opener resources."""

    def __init__(self) -> None:
        self._built_openers: BuiltOpeners | None = None

    def build(
        self,
        http_log_callback,
        proxy_url,
        proxy_handler,
        basic_auth_handler,
        ntlm_auth_handler,
        cookie_handler,
        mangle_plugins,
        url_parameter_handler,
        ignore_session_cookies,
    ) -> None:
        self._built_openers = OpenerBuilder(
            http_log_callback,
            proxy_url,
            proxy_handler,
            basic_auth_handler,
            ntlm_auth_handler,
            cookie_handler,
            mangle_plugins,
            url_parameter_handler,
            ignore_session_cookies,
        ).build()

    def close_connections(self) -> None:
        if self._built_openers is None:
            return

        for handler in (
            self._built_openers.http_handler,
            self._built_openers.https_handler,
        ):
            handler.close_all()

    def get_custom_opener(self):
        if self._built_openers is None:
            return None
        return self._built_openers.uri_opener

    def clear_cache(self):
        if self._built_openers is None:
            return True
        return self._built_openers.cache_handler.clear()

    @property
    def http_handler(self):
        return None if self._built_openers is None else self._built_openers.http_handler

    @property
    def https_handler(self):
        return (
            None if self._built_openers is None else self._built_openers.https_handler
        )

    @property
    def cache_handler(self):
        return (
            None if self._built_openers is None else self._built_openers.cache_handler
        )
