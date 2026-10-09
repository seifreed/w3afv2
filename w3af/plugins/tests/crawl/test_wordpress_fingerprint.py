"""
test_wordpress_fingerprint.py

Copyright 2012 Andres Riancho

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

import hashlib
import os
import tempfile
from typing import ClassVar

import pytest

from w3af.core.controllers.exceptions import BaseFrameworkException
from w3af.plugins.crawl.wordpress_fingerprint import (
    FileFingerPrint,
    wordpress_fingerprint,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

WORDPRESS_URL = "http://wordpress/"

STATIC_FILE = "/* TinyMCE 3.4.1 editor stylesheet */"
TARBALL = b"\x1f\x8bwordpress-3.4.1 release archive"

WP_VERSIONS_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<wp-versions>
  <file src="$wp-content$themes/default/style.css">
    <hash md5="00000000000000000000000000000000">
      <version>2.0</version>
    </hash>
  </file>
  <file src="$wp-plugins$tinymce/editor.css">
    <hash md5="{hashlib.md5(STATIC_FILE.encode()).hexdigest()}">
      <version>3.4.1</version>
    </hash>
  </file>
</wp-versions>
"""

RELEASE_DB = f"""this line is not a release
{hashlib.md5(TARBALL).hexdigest()},3.4.1.tar.gz
"""

INDEX = (
    "<html><head>"
    '<meta name="generator" content="WordPress 3.4.1" />'
    '</head><body><a href="about/">About</a></body></html>'
)

README = "<h1>WordPress</h1><br /> Version 3.4.1"


def _write_temp_file(test_case, content, suffix):
    file_descriptor, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(file_descriptor, "w") as temp_file:
        temp_file.write(content)
    test_case.addCleanup(os.unlink, path)
    return path


class TestWordpressFingerprint(PluginTest):

    target_url = WORDPRESS_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(WORDPRESS_URL, INDEX),
        MockResponse(WORDPRESS_URL + "about/", "<html><body>About</body></html>"),
        MockResponse(WORDPRESS_URL + "index.php", INDEX),
        MockResponse(WORDPRESS_URL + "wp-login.php", "<form>Log in</form>"),
        MockResponse(WORDPRESS_URL + "readme.html", README),
        MockResponse(
            WORDPRESS_URL + "wp-content/plugins/tinymce/editor.css",
            STATIC_FILE,
            "text/css",
        ),
        MockResponse(WORDPRESS_URL + "latest.tar.gz", TARBALL, "application/x-gzip"),
    ]

    def test_find_version(self):
        plugins = {
            "crawl": (
                PluginConfig(
                    "wordpress_fingerprint",
                    (
                        "wp_versions_xml",
                        _write_temp_file(self, WP_VERSIONS_XML, ".xml"),
                        PluginConfig.INPUT_FILE,
                    ),
                    (
                        "release_db",
                        _write_temp_file(self, RELEASE_DB, ".db"),
                        PluginConfig.INPUT_FILE,
                    ),
                ),
                PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
            )
        }
        self._scan(self.target_url, plugins)

        infos = self.kb.get("wordpress_fingerprint", "info")

        descriptions = {i.get_desc(with_id=False) for i in infos}
        expected_descriptions = {
            'WordPress version "3.4.1" found in the index header.',
            'WordPress version "3.4.1" found in the readme.html file.',
            (
                'WordPress version "3.4.1" fingerprinted by matching known md5'
                " hashes to HTTP responses of static resources available at"
                " the remote WordPress install."
            ),
            (
                'The sysadmin used WordPress version "3.4.1.tar.gz"'
                " during the installation, which was found by matching"
                ' the contents of "http://wordpress/latest.tar.gz"'
                " with the hashes of known releases. If the sysadmin"
                " did not update wordpress, the current version will"
                " still be the same."
            ),
        }
        self.assertEqual(descriptions, expected_descriptions)


class TestWordpressFingerprintNoWordpress(PluginTest):

    target_url = WORDPRESS_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(WORDPRESS_URL, "<html><body>Static site</body></html>"),
    ]

    def test_no_wordpress_installation(self):
        plugins = {"crawl": (PluginConfig("wordpress_fingerprint"),)}
        self._scan(self.target_url, plugins)

        self.assertEqual(self.kb.get("wordpress_fingerprint", "info"), [])


class TestWordpressVersionsDatabase:
    def test_xml_parsing_case01(self):
        wp_fingerprints = wordpress_fingerprint()._get_wp_fingerprints()
        assert len(wp_fingerprints) > 20

        wp_file_fp = FileFingerPrint(
            "layout2b.css", "baec6b6ccbf71d8dced9f1bf67c751e1", "0.71-gold"
        )
        assert wp_file_fp in wp_fingerprints

    def _plugin_with_versions_xml(self, path):
        plugin = wordpress_fingerprint()
        options = plugin.get_options()
        options["wp_versions_xml"].set_value(path)
        plugin.set_options(options)
        return plugin

    def test_missing_versions_xml(self, tmp_path):
        versions_xml = tmp_path / "wp_versions.xml"
        versions_xml.write_text(WP_VERSIONS_XML)
        plugin = self._plugin_with_versions_xml(str(versions_xml))
        versions_xml.unlink()

        with pytest.raises(BaseFrameworkException, match="Failed to open"):
            plugin._get_wp_fingerprints()

    def test_invalid_versions_xml(self, tmp_path):
        versions_xml = tmp_path / "wp_versions.xml"
        versions_xml.write_text("<wp-versions><file>")
        plugin = self._plugin_with_versions_xml(str(versions_xml))

        with pytest.raises(BaseFrameworkException, match="XML parsing error"):
            plugin._get_wp_fingerprints()

    def test_long_desc(self):
        assert "fingerprinting" in wordpress_fingerprint().get_long_desc()
