"""Build the configurable options exposed by the HTTP opener."""

from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.options.option_types import (
    BOOL,
    INT,
    POSITIVE_INT,
    STRING,
    URL_LIST,
)


class OpenerOptions:
    """Create the option list for HTTP settings."""

    def __init__(self, configuration) -> None:
        self._configuration = configuration

    def get_options(self):
        """
        :return: A list of option objects for this plugin.
        """
        ol = OptionList()

        d = "HTTP connection timeout"
        h = (
            "The default value of zero indicates that the timeout will be"
            " auto-adjusted based on the average response times from the"
            " application. When set to a value different than zero it is"
            " the number of seconds to wait for a response form the server"
            " before timing out. Set low timeouts for LAN use and high"
            " timeouts for slow Internet connections."
        )
        o = opt_factory(
            "timeout", self._configuration.get("configured_timeout"), d, INT, help=h
        )
        ol.add(o)

        d = (
            "HTTP headers filename which contains additional headers to be"
            " added in each request"
        )
        o = opt_factory(
            "headers_file", self._configuration.get("headers_file"), d, STRING
        )
        ol.add(o)

        d = "Basic authentication username"
        o = opt_factory(
            "basic_auth_user",
            self._configuration.get("basic_auth_user"),
            d,
            STRING,
            tabid="Basic HTTP Authentication",
        )
        ol.add(o)

        d = "Basic authentication password"
        o = opt_factory(
            "basic_auth_passwd",
            self._configuration.get("basic_auth_passwd"),
            d,
            STRING,
            tabid="Basic HTTP Authentication",
        )
        ol.add(o)

        d = "Basic authentication domain"
        h = (
            "This configures on which requests to send the authentication"
            " settings configured in basic_auth_passwd and basic_auth_user."
            " If you are unsure, just set it to the target domain name."
        )
        o = opt_factory(
            "basic_auth_domain",
            self._configuration.get("basic_auth_domain"),
            d,
            STRING,
            help=h,
            tabid="Basic HTTP Authentication",
        )
        ol.add(o)

        d = "NTLM authentication domain (windows domain name)"
        h = "Note that only NTLM v1 is supported."
        o = opt_factory(
            "ntlm_auth_domain",
            self._configuration.get("ntlm_auth_domain"),
            d,
            STRING,
            help=h,
            tabid="NTLM Authentication",
        )
        ol.add(o)

        d = "NTLM authentication username"
        o = opt_factory(
            "ntlm_auth_user",
            self._configuration.get("ntlm_auth_user"),
            d,
            STRING,
            tabid="NTLM Authentication",
        )
        ol.add(o)

        d = "NTLM authentication password"
        o = opt_factory(
            "ntlm_auth_passwd",
            self._configuration.get("ntlm_auth_passwd"),
            d,
            STRING,
            tabid="NTLM Authentication",
        )
        ol.add(o)

        d = "NTLM authentication domain (target domain name)"
        h = (
            "This configures on which requests to send the authentication"
            " settings configured in ntlm_auth_passwd and ntlm_auth_user."
            " If you are unsure, just set it to the target domain name."
        )
        o = opt_factory(
            "ntlm_auth_url",
            self._configuration.get("ntlm_auth_url"),
            d,
            STRING,
            tabid="NTLM Authentication",
            help=h,
        )
        ol.add(o)

        d = "Cookie Jar file holding HTTP cookies"
        h = (
            "The cookiejar file MUST be in Mozilla format. An example of a"
            " valid Mozilla cookie jar file follows:\n\n"
            "# Netscape HTTP Cookie File\n"
            ".domain.com    TRUE   /       FALSE   1731510001"
            "      user    admin\n\n"
            "Please note that the comment is mandatory and the fields need"
            " to be separated using tabs.\n\n"
            "It is also important to note that loaded cookies will only be"
            " sent if all conditions are met. For example, secure cookies"
            " will only be sent over HTTPS and cookie expiration time will"
            " influence if a cookie is sent or not.\n\n"
            "Remember: Session cookies which are stored in cookie jars have"
            " their session expiration set to 0, which will prevent them from"
            " being sent."
        )
        o = opt_factory(
            "cookie_jar_file",
            self._configuration.get("cookie_jar_file"),
            d,
            STRING,
            help=h,
            tabid="Cookies",
        )
        ol.add(o)

        d = "Ignore session cookies"
        h = (
            "If set to True, w3af will not extract cookies from HTTP responses"
            " nor send HTTP cookies in requests."
        )
        o = opt_factory(
            "ignore_session_cookies",
            self._configuration.get("ignore_session_cookies"),
            d,
            "boolean",
            help=h,
            tabid="Cookies",
        )
        ol.add(o)

        d = "Proxy TCP port"
        h = (
            "TCP port for the HTTP proxy. On Microsoft Windows systems,"
            " w3af will use Internet Explorer's proxy settings"
        )
        o = opt_factory(
            "proxy_port",
            self._configuration.get("proxy_port"),
            d,
            INT,
            help=h,
            tabid="Outgoing proxy",
        )
        ol.add(o)

        d = "Proxy IP address"
        h = (
            "IP address for the HTTP proxy. On Microsoft Windows systems,"
            " w3af will use Internet Explorer's proxy settings"
        )
        o = opt_factory(
            "proxy_address",
            self._configuration.get("proxy_address"),
            d,
            STRING,
            help=h,
            tabid="Outgoing proxy",
        )
        ol.add(o)

        d = "User Agent header"
        h = "User Agent header to send in HTTP requests"
        o = opt_factory(
            "user_agent",
            self._configuration.get("user_agent"),
            d,
            STRING,
            help=h,
            tabid="Misc",
        )
        ol.add(o)

        d = "Use random User-Agent header"
        h = (
            "Enable to make w3af choose a random user agent for each HTTP"
            " request sent to the target web application"
        )
        o = opt_factory(
            "rand_user_agent",
            self._configuration.get("rand_user_agent"),
            d,
            BOOL,
            help=h,
            tabid="Misc",
        )
        ol.add(o)

        d = "Maximum file size"
        h = (
            "Indicates the maximum file size (in bytes) that w3af will"
            " retrieve from the remote server"
        )
        o = opt_factory(
            "max_file_size",
            self._configuration.get("max_file_size"),
            d,
            INT,
            help=h,
            tabid="Misc",
        )
        ol.add(o)

        d = "Maximum number of HTTP request retries"
        h = "Indicates the maximum number of retries when requesting an URL"
        o = opt_factory(
            "max_http_retries",
            self._configuration.get("max_http_retries"),
            d,
            INT,
            help=h,
            tabid="Misc",
        )
        ol.add(o)

        d = "Maximum HTTP requests per second"
        h = (
            "Indicates the maximum HTTP requests per second to send. A value"
            " of zero indicates no limit"
        )
        o = opt_factory(
            "max_requests_per_second",
            self._configuration.get("max_requests_per_second"),
            d,
            POSITIVE_INT,
            help=h,
            tabid="Misc",
        )
        ol.add(o)

        d = "Comma separated list of URLs which will always be detected as" " 404 pages"
        o = opt_factory(
            "always_404",
            self._configuration.get("always_404"),
            d,
            URL_LIST,
            tabid="404 settings",
        )
        ol.add(o)

        d = "Comma separated list of URLs which will never be detected as" " 404 pages"
        o = opt_factory(
            "never_404",
            self._configuration.get("never_404"),
            d,
            URL_LIST,
            tabid="404 settings",
        )
        ol.add(o)

        d = "Tag HTTP response as 404 if the string is found in it's body"
        o = opt_factory(
            "string_match_404",
            self._configuration.get("string_match_404"),
            d,
            STRING,
            tabid="404 settings",
        )
        ol.add(o)

        d = "URL parameter (http://host.tld/path;<parameter>)"
        h = (
            "Appends the given URL parameter to every accessed URL."
            " Example: http://www.foobar.com/index.jsp;<parameter>?id=2"
        )
        o = opt_factory(
            "url_parameter", self._configuration.get("url_parameter"), d, STRING, help=h
        )
        ol.add(o)

        return ol
