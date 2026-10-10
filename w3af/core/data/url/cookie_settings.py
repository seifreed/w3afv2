"""Configure and manage the cookie handler used by the HTTP opener."""

import http.cookiejar
from collections.abc import Callable

from w3af.core.data.misc.cookie_jar import ImprovedMozillaCookieJar
from w3af.core.data.url.handlers.cookie_handler import CookieHandler
from w3af.core.exceptions import BaseFrameworkException


class CookieSettings:
    """Manage the default cookie jar and browser session jars."""

    def __init__(self, configuration, log_debug: Callable[..., None]) -> None:
        self._configuration = configuration
        self._log_debug = log_debug
        self.cookie_handler = CookieHandler(ImprovedMozillaCookieJar())

    def set_cookie_jar_file(self, cookiejar_file) -> None:
        if not cookiejar_file:
            return

        cookie_jar = ImprovedMozillaCookieJar()

        try:
            cookie_jar.load(cookiejar_file)
        except http.cookiejar.LoadError as error:
            if "invalid Netscape format cookies file" in str(error):
                docs_url = (
                    "http://docs.w3af.org/en/latest/"
                    "authentication.html#setting-http-cookie"
                )
                msg = (
                    "The supplied cookiejar file is not in Netscape format"
                    " please review our documentation at %s to better"
                    " understand the required format."
                )
                raise BaseFrameworkException(msg % docs_url)

            msg = 'Error while loading cookiejar file. Description: "%s".'
            raise BaseFrameworkException(msg % error)
        except OSError:
            raise BaseFrameworkException(
                "The specified cookie jar file does not exist."
            )

        self.cookie_handler = CookieHandler(cookie_jar)
        self._configuration.save("cookie_jar_file", cookiejar_file)

        if not len(cookie_jar):
            msg = (
                "Did not load any cookies from the cookie jar file."
                " This usually happens when there are no cookies in"
                " the file, the cookies have expired or the file is not"
                " in the expected format."
            )
            raise BaseFrameworkException(msg)

        self._log_debug("Loaded the following cookies:")
        for cookie in cookie_jar:
            self._log_debug("%s", cookie)

    def get_cookies(self):
        return self.cookie_handler.default_cookiejar

    def clear_cookies(self) -> None:
        self.cookie_handler.clear_cookies()
