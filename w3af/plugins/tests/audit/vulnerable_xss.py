"""
vulnerable_xss.py

Copyright 2026 w3af contributors

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

import email
import string
import threading
import urllib.parse

from w3af.plugins.tests.audit.vulnerable_responses import html_page, request_params


def multipart_params(request, files_only=False):
    """
    :param files_only: Ignore the parts which are not file uploads
    :return: A dict with the content of every part of a multipart body, the
             uploaded file contents included.
    """
    content_type = request.headers.get("Content-Type", "")
    raw = f"Content-Type: {content_type}\r\n\r\n".encode() + request.body
    message = email.message_from_bytes(raw)

    params = {}
    for part in message.walk():
        name = part.get_param("name", header="content-disposition")
        is_file = part.get_filename() is not None
        if name is not None and (is_file or not files_only):
            payload = part.get_payload(decode=True)
            params[name] = payload.decode("utf-8", errors="replace")

    return params


def all_params(request, files_only=False):
    if request.headers.get("Content-Type", "").startswith("multipart/"):
        return multipart_params(request, files_only)
    return request_params(request)


def strip_quotes(value):
    return value.replace('"', "").replace("'", "")


def remove_script_tags(value):
    return value.replace("<script", "")


def remove_backticks(value):
    return value.replace("`", "")


class EchoPage:
    """
    A page which writes the request parameters into an HTML template without
    escaping them. The $name placeholders of the template are replaced with
    the value of the request parameter with that name.

    :param template: The HTML page, placeholders are $name
    :param transform: A filter the application applies to the parameters
    :param headers: Extra response headers
    :param status: The response HTTP status code
    :param files_only: Only echo the content of uploaded files
    """

    def __init__(
        self, template, transform=None, headers=None, status=200, files_only=False
    ):
        self.files_only = files_only
        self.template = string.Template(template)
        self.transform = transform
        self.headers = headers or {}
        self.status = status

    def __call__(self, mock_response, request, uri, response_headers):
        params = all_params(request, self.files_only)

        if self.transform is not None:
            params = {name: self.transform(value) for name, value in params.items()}

        body = self.template.safe_substitute(params)
        status, headers, body = html_page(response_headers, body, status=self.status)
        headers.update(self.headers)
        return status, headers, body


class GuestBook:
    """
    A page which stores the text it receives in a POST request and shows all
    the stored texts, without escaping them, when it is requested with GET.
    """

    FORM = (
        '<form method="POST" action="">'
        '<input type="text" name="text" value="hello"/>'
        '<input type="submit" name="Submit" value="Submit"/></form>'
    )

    def __init__(self, headers=None):
        self.headers = headers or {}
        self._texts = []
        self._lock = threading.Lock()

    def __call__(self, mock_response, request, uri, response_headers):
        if request.command == "POST":
            with self._lock:
                self._texts.append(request_params(request).get("text", ""))
            return html_page(response_headers, "Saved")

        with self._lock:
            texts = "".join(f"<p>{text}</p>" for text in self._texts)

        status, headers, body = html_page(response_headers, self.FORM + texts)
        headers.update(self.headers)
        return status, headers, body


class RedirectWithQuery:
    """
    A page which redirects to another page, passing along its query string and
    adding a parameter of its own. The body of the redirect echoes the request
    parameters, as many applications do.
    """

    def __init__(self, target_url, body_template, added_param="added=1"):
        self.target_url = target_url
        self.added_param = added_param
        self.body = EchoPage(body_template, status=302)

    def __call__(self, mock_response, request, uri, response_headers):
        query = urllib.parse.urlsplit(request.uri).query
        query = f"{query}&{self.added_param}" if query else self.added_param
        response_headers["Location"] = f"{self.target_url}?{query}"
        return self.body(mock_response, request, uri, response_headers)
