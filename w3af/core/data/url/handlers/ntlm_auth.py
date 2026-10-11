# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>
# or <http://www.gnu.org/licenses/lgpl.txt>.

import base64
import importlib
import struct
import urllib.error
import urllib.request
from typing import Any

spnego: Any = importlib.import_module("spnego")
SpnegoError: Any = importlib.import_module("spnego.exceptions").SpnegoError

MAX_RETRIES = 3


class HTTPNtlmAuthHandler(urllib.request.BaseHandler):
    """
    urllib handler for NTLM authentication.

    NTLM authenticates the TCP connection, not the request: the message that
    answers the server's challenge must travel on the connection that received
    the challenge. The handler asks the keep-alive connection manager for that
    connection through HTTPRequest.preferred_connection.
    """

    auth_header = "Authorization"

    def __init__(self, password_mgr=None):
        if password_mgr is None:
            password_mgr = urllib.request.HTTPPasswordMgr()
        self.passwd = password_mgr
        self.add_password = self.passwd.add_password
        self.retried = 0

    def http_request(self, request):
        if request.get_header(self.auth_header, None) is not None:
            return request

        credentials = self._find_credentials(request.get_full_url())
        if credentials is not None:
            negotiate = self._client(*credentials).step()
            request.add_unredirected_header(self.auth_header, _ntlm(negotiate))
        return request

    https_request = http_request

    def http_response(self, request, response):
        """
        Answer NTLM challenges while processing the response: w3af's opener
        replaces urllib's HTTPErrorProcessor (see NoOpErrorHandler), so a
        http_error_401() method would never be called.
        """
        if response.code != 401:
            return response

        authenticate = self._answer_challenge(
            request.get_full_url(), response.info().get("www-authenticate", "")
        )
        if authenticate is None:
            return response

        if self.retried > MAX_RETRIES:
            raise urllib.error.HTTPError(
                request.get_full_url(), 401, "NTLM auth failed", response.info(), None
            )
        self.retried += 1

        # Release the challenged connection to the pool and send the
        # authenticated message on it
        response.read()
        response.close()
        request.preferred_connection = response.connection
        request.add_unredirected_header(self.auth_header, authenticate)

        try:
            return self.parent.open(request, timeout=request.timeout)
        finally:
            request.preferred_connection = None
            self.retried = 0

    https_response = http_response

    def _find_credentials(self, url):
        user, password = self.passwd.find_user_password(None, url)
        if password is None:
            return None
        return user, password

    @staticmethod
    def _client(user, password):
        domain, _, username = user.rpartition("\\")
        user = f"{domain}\\{username}" if domain else username
        return spnego.client(user, password, protocol="ntlm")

    def _answer_challenge(self, url, authenticate_header):
        """
        :return: The Authorization header value answering the NTLM challenge
                 in authenticate_header, or None when there is no challenge we
                 can answer.
        """
        credentials = self._find_credentials(url)
        if credentials is None:
            return None

        try:
            ntlm_challenge = next(
                challenge.strip().split(None, 1)[1]
                for challenge in authenticate_header.split(",")
                if challenge.strip().lower().startswith("ntlm ")
            )
            challenge = base64.b64decode(ntlm_challenge, validate=True)
            context = self._client(*credentials)
            context.step()
            return _ntlm(context.step(challenge))
        except (ValueError, StopIteration, struct.error, SpnegoError):
            return None


def _ntlm(token):
    return f"NTLM {base64.b64encode(token).decode('ascii')}"
