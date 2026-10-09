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
import struct
import urllib.error
import urllib.request

import spnego
from spnego.exceptions import SpnegoError


class AbstractNtlmAuthHandler(urllib.request.BaseHandler):
    """
    urllib handler for NTLM authentication.
    """

    auth_header = None

    def __init__(self, password_mgr=None):
        if password_mgr is None:
            password_mgr = urllib.request.HTTPPasswordMgr()
        self.passwd = password_mgr
        self.add_password = self.passwd.add_password
        self.retried = 0

    def reset_retry_count(self):
        self.retried = 0

    def http_request(self, request):
        ntlm_auth_header = request.get_header(self.auth_header, None)
        if ntlm_auth_header is None:
            user, pw = self.passwd.find_user_password(None, request.get_full_url())
            if pw is not None:
                domain, username = self._split_user(user)
                user = f"{domain}\\{username}" if domain else username
                context = spnego.client(user, pw, protocol="ntlm")
                token = base64.b64encode(context.step()).decode("ascii")
                auth = f"NTLM {token}"
                request.add_unredirected_header(self.auth_header, auth)
        return request

    https_request = http_request

    def http_error_auth_reqed(self, auth_header_field, url, req, headers):
        if self.retried > 3:
            # Don't fail endlessly - if we failed once, we'll probably
            # fail a second time. Hm. Unless the Password Manager is
            # prompting for the information. Crap. This isn't great
            # but it's better than the current 'repeat until recursion
            # depth exceeded' approach <wink>
            raise urllib.error.HTTPError(
                req.get_full_url(), 401, "NTLM auth failed", headers, None
            )
        else:
            self.retried += 1

        auth_header_value = headers.get(auth_header_field, None)

        if (
            auth_header_field
            and auth_header_value
            and "ntlm" in auth_header_value.lower()
        ):
            return self.retry_using_http_NTLM_auth(
                req, auth_header_field, None, headers
            )

    @staticmethod
    def _split_user(user):
        if "\\" in user:
            return user.split("\\", 1)
        return None, user

    def retry_using_http_NTLM_auth(self, request, auth_header_field, realm, headers):
        auth_header_value = headers.get(auth_header_field, None)
        if auth_header_value is not None:
            try:
                ntlm_challenge = next(
                    challenge.strip().split(None, 1)[1]
                    for challenge in auth_header_value.split(",")
                    if challenge.strip().lower().startswith("ntlm ")
                )
                challenge = base64.b64decode(ntlm_challenge, validate=True)
                user, password = self.passwd.find_user_password(
                    None, request.get_full_url()
                )
                if password is None:
                    return None
                domain, username = self._split_user(user)
                user = f"{domain}\\{username}" if domain else username
                context = spnego.client(user, password, protocol="ntlm")
                context.step()
                response = base64.b64encode(context.step(challenge)).decode("ascii")
            except (ValueError, StopIteration, struct.error, SpnegoError):
                # Invalid protocol
                return None
            else:
                auth = f"NTLM {response}"
                request.add_unredirected_header(self.auth_header, auth)
                return self.parent.open(request, timeout=request.timeout)
        else:
            return None


class HTTPNtlmAuthHandler(AbstractNtlmAuthHandler):

    auth_header = "Authorization"

    def http_error_401(self, req, fp, code, msg, headers):
        url = req.get_full_url()
        response = self.http_error_auth_reqed("www-authenticate", url, req, headers)
        self.reset_retry_count()
        return response
