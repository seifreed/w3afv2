"""
test_find_captchas.py

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

import itertools
import re
import unittest
from typing import ClassVar

from w3af.plugins.crawl.find_captchas import find_captchas
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

BASE_URL = "http://mock/w3af/crawl/find_captcha/"

PNG_HEADER = b"\x89PNG\r\n\x1a\n"

CAPTCHA_PAGE = (
    "<html><body>"
    '<img src="securimage_show.php"><img src="logo.png">'
    '<a href="register.html">register</a>'
    '<a href="changing.html">changing</a>'
    '<a href="logo.png">logo</a>'
    "</body></html>"
)

REGISTER_PAGE = '<html><body><img src="securimage_show.php"></body></html>'


def _png(content):
    return PNG_HEADER + content


def _new_captcha_responder():
    counter = itertools.count()

    def captcha(mock_response, request, uri, response_headers):
        response_headers["Content-Type"] = "image/png"
        return 200, response_headers, _png(str(next(counter)).encode())

    return captcha


def _new_growing_page_responder():
    """
    Each request for the page adds one more image to it, so two consecutive
    requests never have the same number of images.
    """
    counter = itertools.count()

    def growing_page(mock_response, request, uri, response_headers):
        response_headers["Content-Type"] = "text/html"
        image_count = next(counter)
        images = "".join(f'<img src="growing{i}.png">' for i in range(image_count))
        return 200, response_headers, f"<html><body>{images}</body></html>"

    return growing_page


class TestFindCAPTCHAS(PluginTest):

    target_url = BASE_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(BASE_URL, CAPTCHA_PAGE),
        MockResponse(BASE_URL + "register.html", REGISTER_PAGE),
        MockResponse(BASE_URL + "changing.html", _new_growing_page_responder()),
        MockResponse(BASE_URL + "securimage_show.php", _new_captcha_responder()),
        MockResponse(
            re.compile(re.escape(BASE_URL) + r"(logo|growing\d+)\.png"),
            _png(b"static image"),
            content_type="image/png",
        ),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": BASE_URL,
            "plugins": {
                "crawl": (
                    PluginConfig("find_captchas"),
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                )
            },
        }
    }

    def test_find_captcha(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        infos = self.kb.get("find_captchas", "CAPTCHA")

        self.assertEqual(len(infos), 1, infos)

        info = infos[0]

        self.assertEqual(info.get_name(), "Captcha image detected")
        self.assertEqual(
            info.get_url().url_string, self.target_url + "securimage_show.php"
        )

        requested_paths = [request.path for request in self.received_requests]
        self.assertGreaterEqual(
            requested_paths.count("/w3af/crawl/find_captcha/changing.html"), 2
        )


class TestFindCAPTCHASDescription(unittest.TestCase):
    def test_long_description(self):
        self.assertIn("CAPTCHA", find_captchas().get_long_desc())
