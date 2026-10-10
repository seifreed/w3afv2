"""Configure HTTP basic and NTLM authentication handlers."""

import urllib.request

from w3af.core.data.url.handlers.fast_basic_auth import FastHTTPBasicAuthHandler
from w3af.core.data.url.handlers.ntlm_auth import HTTPNtlmAuthHandler
from w3af.core.exceptions import BaseFrameworkException


class AuthenticationSettings:
    """Manage authentication credentials and their urllib handlers."""

    def __init__(self, configuration, mark_needs_update) -> None:
        self._configuration = configuration
        self._mark_needs_update = mark_needs_update
        self._password_manager: (
            urllib.request.HTTPPasswordMgrWithDefaultRealm | None
        ) = None
        self.basic_auth_handler: FastHTTPBasicAuthHandler | None = None
        self.ntlm_auth_handler: HTTPNtlmAuthHandler | None = None

    @property
    def password_manager(self):
        return self._password_manager

    def set_basic_auth(self, url, username, password) -> None:
        if not url:
            if url is None:
                raise BaseFrameworkException(
                    "The entered basic_auth_domain URL is invalid!"
                )
            if username or password:
                msg = (
                    "To properly configure the basic authentication settings,"
                    " you should also set the auth domain. If you are unsure,"
                    " you can set it to the target domain name"
                    " (eg. www.target.com)"
                )
                raise BaseFrameworkException(msg)
        else:
            if self._password_manager is None:
                self._password_manager = (
                    urllib.request.HTTPPasswordMgrWithDefaultRealm()
                )

            domain = url.get_domain()
            self._password_manager.add_password(None, domain, username, password)
            self.basic_auth_handler = FastHTTPBasicAuthHandler(self._password_manager)
            self._mark_needs_update()

        self._configuration.save("basic_auth_passwd", password)
        self._configuration.save("basic_auth_user", username)
        self._configuration.save("basic_auth_domain", url)

    def set_ntlm_auth(self, url, ntlm_domain, username, password) -> None:
        self._configuration.save("ntlm_auth_passwd", password)
        self._configuration.save("ntlm_auth_domain", ntlm_domain)
        self._configuration.save("ntlm_auth_user", username)
        self._configuration.save("ntlm_auth_url", url)

        if self._password_manager is None:
            self._password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()

        username = ntlm_domain + "\\" + username
        self._password_manager.add_password(None, url, username, password)
        self.ntlm_auth_handler = HTTPNtlmAuthHandler(self._password_manager)
        self._mark_needs_update()
