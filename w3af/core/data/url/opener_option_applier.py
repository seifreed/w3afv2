"""Apply user-provided HTTP opener options."""

from w3af.core.data.parsers.doc.url import URL


class OpenerOptionApplier:
    """Coordinate option changes across the opener settings policies."""

    def __init__(
        self,
        configuration,
        authentication,
        proxy,
        cookies,
        headers,
        request_limits,
        url_parameter,
        set_rand_user_agent,
    ) -> None:
        self._configuration = configuration
        self._authentication = authentication
        self._proxy = proxy
        self._cookies = cookies
        self._headers = headers
        self._request_limits = request_limits
        self._url_parameter = url_parameter
        self._set_rand_user_agent = set_rand_user_agent

    def apply(self, options_list) -> None:
        def get_opt_value(name):
            return options_list[name].get_value()

        self._request_limits.set_configured_timeout(get_opt_value("timeout"))

        basic_auth_domain = get_opt_value("basic_auth_domain")
        basic_auth_user = get_opt_value("basic_auth_user")
        basic_auth_pass = get_opt_value("basic_auth_passwd")

        if (
            basic_auth_domain != self._configuration["basic_auth_domain"]
            or basic_auth_user != self._configuration["basic_auth_user"]
            or basic_auth_pass != self._configuration["basic_auth_passwd"]
        ):
            try:
                basic_auth_domain = URL(basic_auth_domain) if basic_auth_domain else ""
            except ValueError:
                basic_auth_domain = None

            self._authentication.set_basic_auth(
                basic_auth_domain, basic_auth_user, basic_auth_pass
            )

        ntlm_auth_domain = get_opt_value("ntlm_auth_domain")
        ntlm_auth_user = get_opt_value("ntlm_auth_user")
        ntlm_auth_passwd = get_opt_value("ntlm_auth_passwd")
        ntlm_auth_url = get_opt_value("ntlm_auth_url")

        if (
            ntlm_auth_domain != self._configuration["ntlm_auth_domain"]
            or ntlm_auth_user != self._configuration["ntlm_auth_user"]
            or ntlm_auth_passwd != self._configuration["ntlm_auth_passwd"]
            or ntlm_auth_url != self._configuration["ntlm_auth_url"]
        ):
            self._authentication.set_ntlm_auth(
                ntlm_auth_url,
                ntlm_auth_domain,
                ntlm_auth_user,
                ntlm_auth_passwd,
            )

        proxy_address = get_opt_value("proxy_address")
        proxy_port = get_opt_value("proxy_port")

        if (
            proxy_address != self._configuration["proxy_address"]
            or proxy_port != self._configuration["proxy_port"]
        ):
            self._proxy.set_proxy(proxy_address, proxy_port)

        self._cookies.set_cookie_jar_file(get_opt_value("cookie_jar_file"))
        self._headers.set_headers_file(get_opt_value("headers_file"))
        self._headers.set_user_agent(get_opt_value("user_agent"))
        self._set_rand_user_agent(get_opt_value("rand_user_agent"))
        self._configuration["ignore_session_cookies"] = get_opt_value(
            "ignore_session_cookies"
        )

        self._request_limits.set_max_file_size(get_opt_value("max_file_size"))
        self._request_limits.set_max_http_retries(get_opt_value("max_http_retries"))
        self._request_limits.set_max_requests_per_second(
            get_opt_value("max_requests_per_second")
        )

        self._url_parameter.set_url_parameter(get_opt_value("url_parameter"))
        self._configuration["never_404"] = get_opt_value("never_404")
        self._configuration["always_404"] = get_opt_value("always_404")
        self._configuration["string_match_404"] = get_opt_value("string_match_404")
