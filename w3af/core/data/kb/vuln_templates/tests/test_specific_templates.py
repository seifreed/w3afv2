"""
test_specific_templates.py

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

import unittest

from w3af.core.data.dc.multipart_container import MultipartContainer
from w3af.core.data.kb.vuln_templates.dav_template import DAVTemplate
from w3af.core.data.kb.vuln_templates.file_upload_template import (
    FileUploadTemplate,
)
from w3af.core.data.kb.vuln_templates.local_file_read_template import (
    LocalFileReadTemplate,
)
from w3af.core.data.kb.vuln_templates.os_commanding_template import (
    OSCommandingTemplate,
)
from w3af.core.data.kb.vuln_templates.tests.test_base_template import configure
from w3af.core.data.parsers.doc.url import URL


class TestDAVTemplate(unittest.TestCase):
    def test_options(self):
        template = DAVTemplate()
        options = template.get_options()

        self.assertEqual(options["name"].get_value(), "DAV Misconfiguration")

        options["name"].set_value("Writable DAV")
        options["url"].set_value("http://host.tld/dav/")
        template.set_options(options)

        vuln = template.create_vuln()
        self.assertEqual(vuln.get_name(), "Writable DAV")
        self.assertEqual(vuln.get_url(), URL("http://host.tld/dav/"))


class TestFileUploadTemplate(unittest.TestCase):
    def test_create_vuln(self):
        template = configure(
            FileUploadTemplate(),
            data="upload=x&title=abc",
            method="POST",
            vulnerable_parameter="upload",
            file_vars="upload",
            file_dest="http://host.tld/uploads/",
        )

        vuln = template.create_vuln()
        container = vuln.get_mutant().get_dc()

        self.assertIsInstance(container, MultipartContainer)
        self.assertEqual(container.get_file_vars(), ["upload"])
        self.assertEqual(container["title"], ["abc"])
        self.assertEqual(vuln["file_vars"], ["upload"])
        self.assertEqual(vuln["file_dest"], URL("http://host.tld/uploads/"))
        self.assertEqual(vuln.get_token_name(), "upload")


class TestLocalFileReadTemplate(unittest.TestCase):
    def test_create_vuln(self):
        template = configure(
            LocalFileReadTemplate(),
            data="file=a.txt",
            vulnerable_parameter="file",
            payload="../../etc/passwd",
            file_pattern="root:",
        )

        vuln = template.create_vuln()

        self.assertEqual(vuln.get_mutant().get_token_value(), "../../etc/passwd")
        self.assertEqual(vuln["file_pattern"], "root:")


class TestOSCommandingTemplate(unittest.TestCase):
    def test_create_vuln(self):
        template = configure(
            OSCommandingTemplate(),
            data="cmd=ls",
            vulnerable_parameter="cmd",
            separator=";",
            operating_system="windows",
        )

        vuln = template.create_vuln()

        self.assertEqual(vuln["separator"], ";")
        self.assertEqual(vuln["os"], "windows")
        self.assertEqual(vuln.get_token_name(), "cmd")
