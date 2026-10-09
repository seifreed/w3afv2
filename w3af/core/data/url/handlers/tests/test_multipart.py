"""
test_multipartpost.py

Copyright 2014 Andres Riancho

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

import email.parser
import email.policy
import os
import tempfile
import unittest

from w3af.core.data.dc.headers import Headers
from w3af.core.data.dc.multipart_container import MultipartContainer
from w3af.core.data.misc.io import NamedStringIO
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.utils.form_params import FormParameters
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer


def upload(request):
    """
    Behave like moth's /core/file_upload/upload.py: report success only when
    the uploadedfile field is a file with the expected content.
    """
    content_type = request.headers.get("Content-Type", "")
    message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
        f"Content-Type: {content_type}\r\n\r\n".encode() + request.body
    )
    for part in message.iter_parts():
        if part.get_param("name", header="content-disposition") != "uploadedfile":
            continue
        if part.get_filename() and part.get_payload(decode=True) == b"file content":
            return Response(body=f"{part.get_filename()} was successfully uploaded")
    return Response(body="upload failed")


class TestMultipartPostUpload(unittest.TestCase):
    """
    In the new architecture I've been working on, the HTTP requests are almost
    completely created by serializing two objects:
        * FuzzableRequest
        * DataContainer (stored in FuzzableRequest._post_data)

    There is a special DataContainer sub-class for MultipartPost file uploads
    called MultipartContainer, which holds variables and files and when
    serialized will be encoded as multipart.

    These test cases try to make sure that the file upload feature works by
    sending a POST request with a MultipartContainer to a local server.
    """

    def setUp(self):
        self.server = RouteServer({"/upload.py": upload}).start()
        self.addCleanup(self.server.stop)
        self.file_upload_url = URL(self.server.url("/upload.py"))
        self.opener = ExtendedUrllib()
        self.addCleanup(self.opener.end)

    def form_params(self):
        form_params = FormParameters()
        form_params.add_field_by_attr_items([("name", "uploadedfile")])
        form_params.add_field_by_attr_items(
            [("name", "MAX_FILE_SIZE"), ("type", "hidden"), ("value", "10000")]
        )
        return form_params

    def post(self, mpc):
        return self.opener.POST(
            self.file_upload_url, data=str(mpc), headers=Headers(mpc.get_headers())
        )

    def test_multipart_without_file(self):
        form_params = self.form_params()
        form_params["uploadedfile"][0] = "this is not a file"

        resp = self.post(MultipartContainer(form_params))

        self.assertNotIn("was successfully uploaded", resp.get_body())

    def test_file_upload(self):
        fd, path = tempfile.mkstemp(suffix=".tmp")
        os.write(fd, b"file content")
        os.close(fd)
        self.addCleanup(os.unlink, path)

        with open(path) as _file:
            self.upload_file(_file)

    def test_stringio_upload(self):
        self.upload_file(NamedStringIO("file content", name="test.txt"))

    def upload_file(self, _file):
        mpc = MultipartContainer(self.form_params())
        mpc["uploadedfile"][0] = _file

        resp = self.post(mpc)

        self.assertIn("was successfully uploaded", resp.get_body())

    def test_upload_file_using_fuzzable_request(self):
        form_params = self.form_params()
        form_params["uploadedfile"][0] = NamedStringIO("file content", name="test.txt")
        mpc = MultipartContainer(form_params)

        freq = FuzzableRequest(self.file_upload_url, post_data=mpc, method="POST")
        resp = self.opener.send_mutant(freq)

        self.assertIn("test.txt was successfully uploaded", resp.get_body())
