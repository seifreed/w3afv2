"""
opener_settings.py

Copyright 2006 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""

import logging

from w3af.core.configurable import Configurable
from w3af.core.data.kb.config import cf as cfg
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.authentication_settings import AuthenticationSettings
from w3af.core.data.url.cookie_settings import CookieSettings
from w3af.core.data.url.header_settings import HeaderSettings
from w3af.core.data.url.opener_defaults import OpenerDefaults
from w3af.core.data.url.opener_lifecycle import OpenerLifecycle
from w3af.core.data.url.opener_options import OpenerOptions
from w3af.core.data.url.proxy_settings import ProxySettings
from w3af.core.data.url.request_limits_settings import RequestLimitsSettings
from w3af.core.data.url.url_parameter_settings import URLParameterSettings

LOGGER = logging.getLogger(__name__)


class OpenerSettings(Configurable):
    """
    This is a urllib2 configuration manager.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    def __init__(self, http_log_callback=None):

        # Set the openers to None
        self._proxy = ProxySettings(cfg, LOGGER.debug)
        self._url_parameter = URLParameterSettings()
        self._lifecycle = OpenerLifecycle()
        self._request_limits = RequestLimitsSettings(cfg)
        self._defaults = OpenerDefaults(cfg)
        self._options = OpenerOptions(cfg)

        self._cookies = CookieSettings(cfg, LOGGER.debug)

        # Openers
        self._http_log_callback = http_log_callback
        self._authentication = AuthenticationSettings(cfg, self._mark_needs_update)

        # Some internal variables
        self.need_update = True

        # to use random Agent in http requests
        self.rand_user_agent = False

        #   which basically is the UA for IE8 running in Windows 7, plus our
        #   website :)
        self._headers = HeaderSettings(cfg, LOGGER.debug)

        # By default, don't mangle any request/responses
        self._mangle_plugins = []

        # User configured variables
        if cfg.get("user_agent") is None:
            # This is the first time we are executed...
            self.set_default_values()

    @property
    def _basic_auth_handler(self):
        return self._authentication.basic_auth_handler

    @property
    def _ntlm_auth_handler(self):
        return self._authentication.ntlm_auth_handler

    @property
    def _password_mgr(self):
        return self._authentication.password_manager

    @property
    def _cookie_handler(self):
        return self._cookies.cookie_handler

    @property
    def _proxy_handler(self):
        return self._proxy.proxy_handler

    @property
    def _url_parameter_handler(self):
        return self._url_parameter.handler

    @property
    def _uri_opener(self):
        return self._lifecycle.get_custom_opener()

    @property
    def _ka_http(self):
        return self._lifecycle.http_handler

    @property
    def _ka_https(self):
        return self._lifecycle.https_handler

    @property
    def _cache_handler(self):
        return self._lifecycle.cache_handler

    @property
    def header_list(self):
        return self._headers.header_list

    @header_list.setter
    def header_list(self, header_list):
        self._headers.header_list = header_list

    def _mark_needs_update(self):
        self.need_update = True

    def set_default_values(self):
        self._defaults.apply()

    def set_headers_file(self, headers_file):
        """
        Sets the special headers to use, this headers are specified in a file by
        the user. The file can have multiple lines, each line should have the
        following structure :
            - HEADER:VALUE_OF_HEADER

        :param headers_file: The filename where the additional headers are
                             specified
        :return: No value is returned.
        """
        self._headers.set_headers_file(headers_file)

    def set_header_list(self, header_list):
        """
        :param header_list: A list of tuples with (header,value) to be added
                            to every request.
        :return: nothing
        """
        self._headers.set_header_list(header_list)

    def close_connections(self):
        self._lifecycle.close_connections()

    def set_cookie_jar_file(self, cookiejar_file):
        self._cookies.set_cookie_jar_file(cookiejar_file)

    def get_cookies(self):
        """
        :return: The cookies that were collected during this scan.
        """
        return self._cookies.get_cookies()

    def clear_cookies(self):
        self._cookies.clear_cookies()

    def set_configured_timeout(self, timeout):
        self._request_limits.set_configured_timeout(timeout)

    def get_configured_timeout(self):
        """
        :return: The user configured setting for timeout
        """
        return self._request_limits.get_configured_timeout()

    def set_user_agent(self, user_agent):
        self._headers.set_user_agent(user_agent)

    def set_rand_user_agent(self, rand_user_agent):
        self.rand_user_agent = rand_user_agent
        cfg.save("rand_user_agent", rand_user_agent)

    def set_proxy(self, ip, port):
        """
        Saves the proxy information and creates the handler.

        If the information is invalid it will set self._proxy_handler to None,
        so no proxy is used.

        :return: None
        """
        self._proxy.set_proxy(ip, port)

    def get_proxy(self):
        return self._proxy.get_proxy()

    def set_basic_auth(self, url, username, password):
        LOGGER.debug("Called set_basic_auth")
        self._authentication.set_basic_auth(url, username, password)

    def set_ntlm_auth(self, url, ntlm_domain, username, password):
        self._authentication.set_ntlm_auth(url, ntlm_domain, username, password)

    def build_openers(self):
        self._lifecycle.build(
            self._http_log_callback,
            self.get_proxy(),
            self._proxy_handler,
            self._basic_auth_handler,
            self._ntlm_auth_handler,
            self._cookie_handler,
            self._mangle_plugins,
            self._url_parameter_handler,
            cfg.get("ignore_session_cookies"),
        )

    def get_custom_opener(self):
        return self._lifecycle.get_custom_opener()

    def clear_cache(self):
        """
        Calls the cache handler and requires it to clear the cache, removing
        files and directories.

        :return: True if the cache was successfully cleared.
        """
        return self._lifecycle.clear_cache()

    def set_mangle_plugins(self, mp):
        """
        Configure the mangle plugins to be used.

        :param mp: A list of mangle plugin instances.
        """
        self._mangle_plugins = mp

    def set_max_file_size(self, max_file_size):
        self._request_limits.set_max_file_size(max_file_size)

    def set_max_http_retries(self, retry_num):
        self._request_limits.set_max_http_retries(retry_num)

    def set_max_requests_per_second(self, max_requests_per_second):
        self._request_limits.set_max_requests_per_second(max_requests_per_second)

    def get_max_requests_per_second(self):
        return self._request_limits.get_max_requests_per_second()

    def get_max_retrys(self):
        return self._request_limits.get_max_retrys()

    def set_url_parameter(self, url_param):
        self._url_parameter.set_url_parameter(url_param)

    def get_options(self):
        return self._options.get_options()

    def set_options(self, options_list):
        """
        This method sets all the options that are configured using the user
        interface generated by the framework using the result of get_options().

        :param options_list: An OptionList with the option objects for a plugin.
        :return: No value is returned.
        """

        def get_opt_value(name):
            return options_list[name].get_value()

        self.set_configured_timeout(get_opt_value("timeout"))

        # Only apply changes if they exist
        bauth_domain = get_opt_value("basic_auth_domain")
        bauth_user = get_opt_value("basic_auth_user")
        bauth_pass = get_opt_value("basic_auth_passwd")

        if (
            bauth_domain != cfg["basic_auth_domain"]
            or bauth_user != cfg["basic_auth_user"]
            or bauth_pass != cfg["basic_auth_passwd"]
        ):
            try:
                bauth_domain = URL(bauth_domain) if bauth_domain else ""
            except ValueError:
                bauth_domain = None

            self.set_basic_auth(bauth_domain, bauth_user, bauth_pass)

        ntlm_auth_domain = get_opt_value("ntlm_auth_domain")
        ntlm_auth_user = get_opt_value("ntlm_auth_user")
        ntlm_auth_passwd = get_opt_value("ntlm_auth_passwd")
        ntlm_auth_url = get_opt_value("ntlm_auth_url")

        if (
            ntlm_auth_domain != cfg["ntlm_auth_domain"]
            or ntlm_auth_user != cfg["ntlm_auth_user"]
            or ntlm_auth_passwd != cfg["ntlm_auth_passwd"]
            or ntlm_auth_url != cfg["ntlm_auth_url"]
        ):
            self.set_ntlm_auth(
                ntlm_auth_url, ntlm_auth_domain, ntlm_auth_user, ntlm_auth_passwd
            )

        # Only apply changes if they exist
        proxy_address = get_opt_value("proxy_address")
        proxy_port = get_opt_value("proxy_port")

        if proxy_address != cfg["proxy_address"] or proxy_port != cfg["proxy_port"]:
            self.set_proxy(proxy_address, proxy_port)

        self.set_cookie_jar_file(get_opt_value("cookie_jar_file"))
        self.set_headers_file(get_opt_value("headers_file"))
        self.set_user_agent(get_opt_value("user_agent"))
        self.set_rand_user_agent(get_opt_value("rand_user_agent"))
        cfg["ignore_session_cookies"] = get_opt_value("ignore_session_cookies")

        self.set_max_file_size(get_opt_value("max_file_size"))
        self.set_max_http_retries(get_opt_value("max_http_retries"))
        self.set_max_requests_per_second(get_opt_value("max_requests_per_second"))

        self.set_url_parameter(get_opt_value("url_parameter"))

        # 404 settings are saved here
        cfg["never_404"] = get_opt_value("never_404")
        cfg["always_404"] = get_opt_value("always_404")
        cfg["string_match_404"] = get_opt_value("string_match_404")

    def get_desc(self):
        return (
            "This section is used to configure URL settings that "
            "affect the core and plugins."
        )
