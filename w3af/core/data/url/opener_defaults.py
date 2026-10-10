"""Persist the default HTTP opener configuration."""

from w3af.core.data.url.constants import MAX_HTTP_RETRIES


class OpenerDefaults:
    """Apply the default values used by the HTTP opener."""

    def __init__(self, configuration) -> None:
        self._configuration = configuration

    def apply(self) -> None:
        self._configuration.save("configured_timeout", 0)
        self._configuration.save("headers_file", "")
        self._configuration.save("cookie_jar_file", "")
        self._configuration.save("user_agent", "w3af.org")
        self._configuration.save("rand_user_agent", False)
        self._configuration.save("proxy_address", "")
        self._configuration.save("proxy_port", 8080)
        self._configuration.save("basic_auth_passwd", "")
        self._configuration.save("basic_auth_user", "")
        self._configuration.save("basic_auth_domain", "")
        self._configuration.save("ntlm_auth_domain", "")
        self._configuration.save("ntlm_auth_user", "")
        self._configuration.save("ntlm_auth_passwd", "")
        self._configuration.save("ntlm_auth_url", "")
        self._configuration.save("ignore_session_cookies", False)
        self._configuration.save("max_file_size", 400000)
        self._configuration.save("max_http_retries", MAX_HTTP_RETRIES)
        self._configuration.save("max_requests_per_second", 0)
        self._configuration.save("url_parameter", "")
        self._configuration.save("never_404", [])
        self._configuration.save("always_404", [])
        self._configuration.save("string_match_404", "")
