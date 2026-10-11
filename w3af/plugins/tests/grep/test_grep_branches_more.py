"""
test_grep_branches_more.py

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

More unit tests for grep plugin code paths the per-plugin modules miss.
"""

import os
import shutil
import tempfile
from pathlib import Path

from w3af import ROOT_PATH
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.exceptions import BaseFrameworkException
from w3af.plugins.grep.html_comments import html_comments
from w3af.plugins.grep.meta_tags import meta_tags
from w3af.plugins.grep.motw import motw
from w3af.plugins.grep.password_profiling import password_profiling
from w3af.plugins.grep.password_profiling_plugins.base_plugin import (
    BasePwdProfilingPlugin,
)
from w3af.plugins.grep.password_profiling_plugins.pdf import pdf
from w3af.plugins.grep.path_disclosure import path_disclosure
from w3af.plugins.grep.private_ip import private_ip
from w3af.plugins.grep.serialized_object import serialized_object
from w3af.plugins.grep.ssn import ssn
from w3af.plugins.grep.ssndata.ssn_areas_groups import areas_groups_map
from w3af.plugins.grep.strange_headers import strange_headers
from w3af.plugins.grep.strange_parameters import strange_parameters
from w3af.plugins.grep.user_defined_regex import user_defined_regex
from w3af.plugins.grep.websockets_links import websockets_links
from w3af.plugins.tests.grep.grep_test_utils import (
    GrepPluginTestCase,
    make_request,
    make_response,
)

TEST_PDF = os.path.join(
    ROOT_PATH, "plugins", "grep", "password_profiling_plugins", "tests", "test.pdf"
)


class TestHTMLCommentsBranches(GrepPluginTestCase):

    def test_unparseable(self):
        plugin = self.configure_plugin(html_comments())
        plugin.grep(make_request(), self.make_unparseable_response())
        self.assertEqual(kb.get("html_comments", "interesting_comments"), [])

    def test_comment_sent_in_request_is_ignored(self):
        plugin = self.configure_plugin(html_comments())
        # Interesting words are matched surrounded by spaces (" pass ")
        comment = " the pass word "
        request = make_request("http://www.w3af.com/?c=%20the%20pass%20word%20")
        plugin.grep(request, make_response(body=f"<!--{comment}-->"))
        self.assertEqual(kb.get("html_comments", "interesting_comments"), [])

    def test_conditional_comments_are_not_html_disclosure(self):
        plugin = self.configure_plugin(html_comments())
        body = '<!-- [if IE] <a href="ie.html">old browser</a> -->'
        plugin.grep(make_request(), make_response(body=body))
        self.assertEqual(kb.get("html_comments", "html_comment_hides_html"), [])


class TestMetaTagsBranches(GrepPluginTestCase):

    def test_404_and_unparseable(self):
        marker = self.mark_as_404()
        plugin = self.configure_plugin(meta_tags())
        body = f'<meta name="author" content="x">{marker}'
        plugin.grep(make_request(), make_response(body=body))
        plugin.grep(make_request(), self.make_unparseable_response())
        plugin.end()
        self.assertEqual(kb.get("meta_tags", "meta_tags"), [])

    def test_interesting_attribute_name(self):
        plugin = self.configure_plugin(meta_tags())
        body = '<html><meta name="" content=""><meta author="pablo"></html>'
        plugin.grep(make_request(), make_response(body=body))
        plugin.end()

        infos = kb.get("meta_tags", "meta_tags")
        self.assertEqual(len(infos), 1)
        self.assertIn("attribute name", infos[0].get_desc())


class TestMOTWBranches(GrepPluginTestCase):

    def test_valid_mark_of_the_web(self):
        plugin = self.configure_plugin(motw())
        body = "<!-- saved from url=(0022)http://www.w3af.com/x/ -->"
        plugin.grep(make_request(), make_response(body=body))
        plugin.end()

        infos = kb.get("motw", "motw")
        self.assertEqual(len(infos), 1)
        self.assertIn("valid mark of the web", infos[0].get_desc())

    def test_malformed_mark_and_404(self):
        marker = self.mark_as_404()
        plugin = self.configure_plugin(motw())
        plugin.grep(make_request(), make_response(body="saved from url=nothing"))
        body = f"<!-- saved from url=(0022)http://www.w3af.com/x/ --> {marker}"
        plugin.grep(make_request(), make_response(body=body, _id=2))
        self.assertEqual(kb.get("motw", "motw"), [])


class TestPasswordProfilingBranches(GrepPluginTestCase):

    def setUp(self):
        super().setUp()
        kb.raw_write("lang", "lang", "en")

    def test_ignored_responses(self):
        marker = self.mark_as_404()
        plugin = self.configure_plugin(password_profiling())
        body = "<html>Unusualword appears here</html>"
        plugin.grep(make_request(), make_response(body=body, code=404))
        plugin.grep(make_request(method="PUT"), make_response(body=body))
        plugin.grep(make_request(), make_response(body=f"{body}{marker}"))

        self.assertEqual(kb.raw_read("password_profiling", "password_profiling"), {})

    def test_large_word_maps_are_trimmed(self):
        plugin = self.configure_plugin(password_profiling())
        words = " ".join(f"word{i:05d}abc" for i in range(2100))
        plugin.grep(make_request(), make_response(body=f"<html>{words}</html>"))

        collected = kb.raw_read("password_profiling", "password_profiling")
        self.assertEqual(len(collected), 1000)


class TestPasswordProfilingPlugins(GrepPluginTestCase):

    def test_base_plugin_requires_get_words(self):
        self.assertRaises(
            BaseFrameworkException,
            BasePwdProfilingPlugin().get_words,
            make_response(),
        )

    def test_pdf_words(self):
        body = Path(TEST_PDF).read_bytes()
        response = make_response(body=body, content_type="application/pdf")

        words = pdf().get_words(response)

        self.assertEqual(words["Testing,"], 1)
        self.assertEqual(words["page"], 1)
        self.assertEqual(words["two."], 1)

    def test_truncated_pdf(self):
        body = Path(TEST_PDF).read_bytes()
        truncated = body[: len(body) // 2]
        response = make_response(body=truncated, content_type="application/pdf")

        self.assertIsNone(pdf().get_words(response))

    def test_not_a_pdf(self):
        self.assertIsNone(pdf().get_words(make_response()))


class TestPathDisclosureBranches(GrepPluginTestCase):

    BODY = "<html> /var/www/foobar/htdocs/article.php </html>"

    def test_shorter_match_of_reported_path_is_ignored(self):
        plugin = self.configure_plugin(path_disclosure())
        plugin.grep(make_request(), make_response(body=self.BODY))
        plugin.grep(make_request(), make_response(body=self.BODY, _id=2))
        shorter = "<html> /htdocs/article.php </html>"
        plugin.grep(make_request(), make_response(body=shorter, _id=3))

        vulns = kb.get("path_disclosure", "path_disclosure")
        self.assertEqual(len(vulns), 1)
        self.assertEqual(vulns[0]["path"], "/var/www/foobar/htdocs/article.php")

    def test_path_sent_in_request(self):
        plugin = self.configure_plugin(path_disclosure())
        url = "http://www.w3af.com/?f=/var/www/foobar/htdocs/article.php"
        plugin.grep(make_request(url), make_response(url, body=self.BODY))
        self.assertEqual(kb.get("path_disclosure", "path_disclosure"), [])

    def test_path_equal_to_known_url_path_has_no_webroot(self):
        plugin = self.configure_plugin(path_disclosure())
        disclosed = "/var/www/index.php"
        plugin.grep(make_request(), make_response(body=f"<p> {disclosed} </p>"))

        kb.add_url(URL(f"http://www.w3af.com{disclosed}"))
        body = "<p> /var/www/other.php </p>"
        plugin.grep(make_request(), make_response(body=body, _id=2))

        self.assertEqual(kb.raw_read("path_disclosure", "webroot"), [])


class TestPrivateIPBranches(GrepPluginTestCase):

    TARGET = "http://10.1.2.3/"

    def test_requested_ip_is_ignored(self):
        plugin = self.configure_plugin(private_ip())
        response = make_response(
            self.TARGET, body="<p>10.1.2.3</p>", headers=[("X-Via", "10.1.2.3")]
        )
        plugin.grep(make_request(self.TARGET), response)

        self.assertEqual(kb.get("private_ip", "header"), [])
        self.assertEqual(kb.get("private_ip", "HTML"), [])

    def test_ip_in_header_name(self):
        plugin = self.configure_plugin(private_ip())
        response = make_response(headers=[("X-10.4.4.4", "yes")])
        plugin.grep(make_request(), response)

        infos = kb.get("private_ip", "header")
        self.assertEqual(len(infos), 1)
        self.assertIn('"None" response header', infos[0].get_desc())

    def test_ignored_ips_in_body(self):
        plugin = self.configure_plugin(private_ip())
        body = "<pre>X-Forwarded-For: 10.5.5.5</pre>\n<p>10.6.6.6</p>"
        url = "http://www.w3af.com/?ip=10.6.6.6"
        plugin.grep(make_request(url), make_response(url, body=body))

        self.assertEqual(kb.get("private_ip", "HTML"), [])


class TestSerializedObjectCache(GrepPluginTestCase):

    def test_cache_is_bounded(self):
        plugin = self.configure_plugin(serialized_object())
        for i in range(serialized_object.CACHE_MAX_SIZE + 5):
            url = f"http://www.w3af.com/?p=value-number-{i:05d}-long-enough"
            plugin.grep(make_request(url), make_response(url, _id=i + 1))

        self.assertLess(len(plugin._cache), serialized_object.CACHE_MAX_SIZE)


class TestSSNValidation(GrepPluginTestCase):

    def _area_with_group(self, predicate):
        for area, group in areas_groups_map.items():
            if group and predicate(group) and area not in (0, 666):
                return area, group
        raise AssertionError("No area matches the predicate")

    def _grep(self, area, group_number):
        body = f"<p> {area:03d}-{group_number:02d}-1234 </p>"
        self.configure_plugin(ssn()).grep(make_request(), make_response(body=body))
        return kb.get("ssn", "ssn")

    def test_little_odd_group(self):
        area, group = self._area_with_group(lambda g: g in range(1, 11, 2))
        self.assertEqual(len(self._grep(area, group)), 1)

    def test_little_even_group(self):
        area, _ = self._area_with_group(lambda g: g in range(2, 10, 2))
        self.assertEqual(len(self._grep(area, 1)), 1)

    def test_group_number_not_issued_yet(self):
        area, group = self._area_with_group(lambda g: g in range(1, 9, 2))
        self.assertEqual(self._grep(area, group + 2), [])

    def test_unassigned_area(self):
        # 666 is missing from the map too, but the SSN regex never matches it
        unassigned = next(
            area
            for area in range(1, 773)
            if area not in areas_groups_map and area != 666
        )
        self.assertEqual(self._grep(unassigned, 1), [])

    def test_non_200(self):
        plugin = self.configure_plugin(ssn())
        body = "<p> 123-45-6789 </p>"
        plugin.grep(make_request(), make_response(body=body, code=500))
        self.assertEqual(kb.get("ssn", "ssn"), [])


class TestStrangeHeadersContentLocation(GrepPluginTestCase):

    def test_content_location_outside_3xx(self):
        plugin = self.configure_plugin(strange_headers())
        response = make_response(headers=[("Content-Location", "/other")])
        plugin.grep(make_request(), response)

        anomalies = kb.get("strange_headers", "anomaly")
        self.assertEqual(len(anomalies), 1)
        self.assertIn("content-location", anomalies[0].get_desc())

    def test_content_location_in_redirect_is_fine(self):
        plugin = self.configure_plugin(strange_headers())
        response = make_response(code=302, headers=[("Content-Location", "/x")])
        plugin.grep(make_request(), response)
        self.assertEqual(kb.get("strange_headers", "anomaly"), [])


class TestStrangeParametersBranches(GrepPluginTestCase):

    def setUp(self):
        super().setUp()
        self.plugin = self.configure_plugin(strange_parameters())

    def _grep(self, href, request_url="http://www.w3af.com/", _id=1):
        body = f'<a href="{href}">link</a>'
        response = make_response(body=body, _id=_id)
        self.plugin.grep(make_request(request_url), response)

    def test_already_reported_parameter(self):
        href = "/x?q=foo(bar)"
        self._grep(href)
        self._grep(href, _id=2)
        self.assertEqual(len(kb.get("strange_parameters", "strange_parameters")), 1)

    def test_values_sent_in_request_are_ignored(self):
        sql = "SELECT a FROM b"
        url = "http://www.w3af.com/?q=foo(bar)&s=SELECT%20a%20FROM%20b"
        self._grep("/x?q=foo(bar)&s=" + sql, request_url=url)
        self.assertEqual(kb.get("strange_parameters", "strange_parameters"), [])

    def test_urls_and_wicket_are_not_strange(self):
        self._grep("/x?u=https://w3af.org/a(b)")
        self._grep("/y?wicket:interface=:0:signInForm::IFormSubmitListener::")
        self.assertEqual(kb.get("strange_parameters", "strange_parameters"), [])


class TestUserDefinedRegexBranches(GrepPluginTestCase):

    def setUp(self):
        super().setUp()
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, True)

    def _plugin(self, single_regex="", regex_file_path=""):
        plugin = self.configure_plugin(user_defined_regex())
        options = plugin.get_options()
        options["single_regex"].set_value(single_regex)
        options["regex_file_path"].set_value(regex_file_path)
        plugin.set_options(options)
        return plugin

    def _regex_file(self, *lines):
        path = os.path.join(self.directory, "regexes.txt")
        Path(path).write_text("\n".join(lines))
        return path

    def test_regexes_from_file(self):
        plugin = self._plugin(regex_file_path=self._regex_file("secret-[0-9]+"))
        long_match = "secret-" + "1" * 30
        plugin.grep(make_request(), make_response(body=long_match, _id=1))
        plugin.grep(make_request(), make_response(body=long_match, _id=2))

        infos = kb.get("user_defined_regex", "user_defined_regex")
        self.assertEqual(len(infos), 1)
        self.assertIn("...", infos[0].get_desc())
        self.assertEqual(infos[0].get_id(), [1, 2])

    def test_ignored_responses(self):
        plugin = self._plugin(single_regex="needle")
        plugin.grep(
            make_request(), make_response(body="needle", content_type="image/png")
        )
        plugin.grep(make_request(), make_response(body="haystack"))
        self.assertEqual(kb.get("user_defined_regex", "user_defined_regex"), [])

    def test_invalid_regex_in_file(self):
        path = self._regex_file("(unbalanced")
        plugin = self.configure_plugin(user_defined_regex())
        options = plugin.get_options()
        options["regex_file_path"].set_value(path)
        self.assertRaises(BaseFrameworkException, plugin.set_options, options)


class TestWebSocketsLinksEmptyScript(GrepPluginTestCase):

    def test_empty_script_tag(self):
        plugin = self.configure_plugin(websockets_links())
        body = "<html><script></script><p>ws://w3af.org/socket</p></html>"
        plugin.grep(make_request(), make_response(body=body))
        self.assertEqual(kb.get("websockets_links", "websockets_links"), [])


kb = DBKnowledgeBase()
