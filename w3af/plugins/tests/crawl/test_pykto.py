"""
test_pykto.py

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

import os
import re
import tempfile
import unittest
from typing import ClassVar

from w3af import ROOT_PATH
from w3af.core.controllers.exceptions import RunOnce
from w3af.core.controllers.threads.threadpool import Pool
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.crawl.pykto import (
    Config,
    IsVulnerableHelper,
    NiktoTestParser,
    pykto,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

DB_PATH = os.path.join(
    ROOT_PATH, "plugins", "tests", "crawl", "pykto", "scan_database.db"
)


def pykto_plugins(mutate_tests):
    return {
        "crawl": (
            PluginConfig(
                "pykto",
                ("db_file", DB_PATH, PluginConfig.INPUT_FILE),
                ("mutate_tests", mutate_tests, PluginConfig.BOOL),
            ),
        )
    }


def site_responses(*hidden_dirs):
    responses = [
        MockResponse("http://mock/w3af/", "index"),
        MockResponse("http://mock/phpinfo.php", "<h1>PHP Version 5.1.6</h1>"),
    ]

    for hidden_dir in hidden_dirs:
        url = f"http://mock{hidden_dir}"
        responses.append(MockResponse(url, "secret", method="HEAD"))
        responses.append(MockResponse(url, "secret"))

    return responses


class TestPykto(PluginTest):

    target_url = "http://mock/w3af/"

    MOCK_RESPONSES: ClassVar[list] = site_responses("/hidden/")

    def test_basic_pykto(self):
        self._scan(self.target_url, pykto_plugins(False))

        vulns = self.kb.get("pykto", "vuln")
        vuln_urls = {v.get_url().url_string for v in vulns}
        self.assertEqual(vuln_urls, {"http://mock/phpinfo.php", "http://mock/hidden/"})

        urls = {u.url_string for u in self.kb.get_all_known_urls()}
        self.assertEqual(urls, {self.target_url} | vuln_urls)

    def test_long_desc(self):
        self.assertIn("nikto", pykto().get_long_desc())


class TestPyktoMutateTests(PluginTest):

    target_url = "http://mock/w3af/"

    MOCK_RESPONSES: ClassVar[list] = site_responses("/hidden/", "/w3af/hidden/")

    def test_mutate_tests_run_in_every_directory(self):
        self._scan(self.target_url, pykto_plugins(True))

        vuln_urls = {v.get_url().url_string for v in self.kb.get("pykto", "vuln")}
        self.assertEqual(
            vuln_urls,
            {
                "http://mock/phpinfo.php",
                "http://mock/hidden/",
                "http://mock/w3af/hidden/",
            },
        )


class TestIsVulnerableHelper(unittest.TestCase):
    # is_vuln = IsVulnerableHelper(match_1, match_1_or, match_1_and,
    #                              fail_1, fail_2)

    def test_checks_only_response_code_case01(self):
        is_vuln = IsVulnerableHelper(200, None, None, None, None)
        self.assertTrue(is_vuln.checks_only_response_code())

    def test_checks_only_response_code_case02(self):
        is_vuln = IsVulnerableHelper(200, 302, None, None, None)
        self.assertTrue(is_vuln.checks_only_response_code())

    def test_checks_only_response_code_case03(self):
        is_vuln = IsVulnerableHelper(200, re.compile("a"), None, None, None)
        self.assertFalse(is_vuln.checks_only_response_code())

    def test_checks_only_response_code_case04(self):
        is_vuln = IsVulnerableHelper(re.compile("a"), re.compile("b"), None, None, None)
        self.assertFalse(is_vuln.checks_only_response_code())

    def test_check_case01(self):
        is_vuln = IsVulnerableHelper(re.compile("abc"), None, None, None, None)
        url = URL("http://moth/")
        http_response = HTTPResponse(200, "hello world abc def", Headers(), url, url)
        self.assertTrue(is_vuln.check(http_response))

    def test_check_case02(self):
        is_vuln = IsVulnerableHelper(re.compile("xyz"), None, None, None, None)
        url = URL("http://moth/")
        http_response = HTTPResponse(200, "hello world abc def", Headers(), url, url)
        self.assertFalse(is_vuln.check(http_response))

    def test_check_case03(self):
        is_vuln = IsVulnerableHelper(
            re.compile("xyz"), re.compile("def"), None, None, None
        )
        url = URL("http://moth/")
        http_response = HTTPResponse(200, "hello world abc def", Headers(), url, url)
        self.assertTrue(is_vuln.check(http_response))

    def test_check_case04(self):
        is_vuln = IsVulnerableHelper(200, re.compile("def"), None, None, None)
        url = URL("http://moth/")
        http_response = HTTPResponse(200, "hello world abc def", Headers(), url, url)
        self.assertTrue(is_vuln.check(http_response))

    def test_check_case05(self):
        is_vuln = IsVulnerableHelper(200, 301, None, None, None)
        url = URL("http://moth/")
        http_response = HTTPResponse(301, "hello world abc def", Headers(), url, url)
        self.assertTrue(is_vuln.check(http_response))

    def test_check_case06(self):
        is_vuln = IsVulnerableHelper(200, 301, re.compile("hello"), None, None)
        url = URL("http://moth/")
        http_response = HTTPResponse(301, "hello world abc def", Headers(), url, url)
        self.assertTrue(is_vuln.check(http_response))

    def test_check_case07(self):
        is_vuln = IsVulnerableHelper(200, 301, re.compile("xyz"), None, None)
        url = URL("http://moth/")
        http_response = HTTPResponse(301, "hello world abc def", Headers(), url, url)
        self.assertFalse(is_vuln.check(http_response))

    def test_check_case08(self):
        is_vuln = IsVulnerableHelper(
            200, 301, re.compile("def"), re.compile("xyz"), re.compile("abc")
        )
        url = URL("http://moth/")
        http_response = HTTPResponse(301, "hello world abc def", Headers(), url, url)
        self.assertFalse(is_vuln.check(http_response))

    def test_check_case09(self):
        is_vuln = IsVulnerableHelper(
            200, 301, re.compile("def"), re.compile("xyz"), re.compile("spam")
        )
        url = URL("http://moth/")
        http_response = HTTPResponse(301, "hello world abc def", Headers(), url, url)
        self.assertTrue(is_vuln.check(http_response))


class TestNiktoTestParser(unittest.TestCase):

    def setUp(self):
        self.pykto_inst = pykto()

    def test_not_too_many_ignores(self):
        config = Config(["/cgi-bin/"], [], [], [], [])
        url = URL("http://moth/")
        pykto_inst = self.pykto_inst
        nikto_parser = NiktoTestParser(pykto_inst._db_file, config, url)

        # Go through all the lines
        generator = nikto_parser.test_generator()
        [i for (i,) in generator]

        self.assertLess(len(nikto_parser.ignored), 30, len(nikto_parser.ignored))

    def test_parse_db_line_basic(self):
        """
        This test reads a line from the DB and parses it, it's objective is to
        make sure that DB upgrades with update_scan_db.py do not break the code
        at pykto.py.
        """
        config = Config(["/cgi-bin/"], [], [], [], [])
        url = URL("http://moth/")
        pykto_inst = self.pykto_inst
        nikto_parser = NiktoTestParser(pykto_inst._db_file, config, url)

        line = (
            '"000003","0","1234576890ab","@CGIDIRScart32.exe","GET","200"'
            ',"","","","","request cart32.exe/cart32clientlist","",""'
        )
        nikto_tests = [i for i in nikto_parser._parse_db_line(line)]

        self.assertEqual(len(nikto_tests), 1)

        nikto_test = nikto_tests[0]

        self.assertEqual(nikto_test.id, "000003")
        self.assertEqual(nikto_test.osvdb, "0")
        self.assertEqual(nikto_test.tune, "1234576890ab")
        self.assertEqual(nikto_test.uri.url_string, "http://moth/cgi-bin/cart32.exe")
        self.assertEqual(nikto_test.method, "GET")
        self.assertEqual(nikto_test.match_1, 200)
        self.assertEqual(nikto_test.match_1_or, None)
        self.assertEqual(nikto_test.match_1_and, None)
        self.assertEqual(nikto_test.fail_1, None)
        self.assertEqual(nikto_test.fail_2, None)
        self.assertEqual(nikto_test.message, "request cart32.exe/cart32clientlist")
        self.assertEqual(nikto_test.data, "")
        self.assertEqual(nikto_test.headers, "")

        generator = nikto_parser.test_generator()
        cart32_test_from_db = next(i for (i,) in generator if i.id == "000003")

        self.assertEqual(cart32_test_from_db.uri, nikto_test.uri)
        self.assertEqual(cart32_test_from_db.match_1, nikto_test.match_1)
        self.assertEqual(cart32_test_from_db.message, nikto_test.message)

    def test_parse_db_line_junk(self):
        config = Config(["/cgi-bin/"], [], [], [], [])
        url = URL("http://moth/")
        pykto_inst = self.pykto_inst
        nikto_parser = NiktoTestParser(pykto_inst._db_file, config, url)

        line = '"0","0","","/docs/JUNK(5)","GET","200"' ',"","","","","","",""'
        nikto_tests = [i for i in nikto_parser._parse_db_line(line)]

        self.assertEqual(len(nikto_tests), 1)

        nikto_test = nikto_tests[0]

        self.assertIn("/docs/", nikto_test.uri.url_string)
        self.assertEqual(len("/docs/") + 5, len(nikto_test.uri.get_path()))

    def test_parse_db_line_no_vars(self):
        config = Config([], [], [], [], [])
        url = URL("http://moth/")
        pykto_inst = self.pykto_inst
        nikto_parser = NiktoTestParser(pykto_inst._db_file, config, url)

        line = '"0","0","","/docs/","GET","200"' ',"","","","","","",""'
        nikto_tests = [i for i in nikto_parser._parse_db_line(line)]

        self.assertEqual(len(nikto_tests), 1)

        nikto_test = nikto_tests[0]

        self.assertEqual("/docs/", nikto_test.uri.get_path())

    def test_parse_db_line_cgidirs(self):
        config = Config(["/cgi-bin/"], [], [], [], [])
        url = URL("http://moth/")
        pykto_inst = self.pykto_inst
        nikto_parser = NiktoTestParser(pykto_inst._db_file, config, url)

        line = '"0","0","","@CGIDIRS","GET","200"' ',"","","","","","",""'
        nikto_tests = [i for i in nikto_parser._parse_db_line(line)]

        self.assertEqual(len(nikto_tests), 1)

        nikto_test = nikto_tests[0]

        self.assertEqual("/cgi-bin/", nikto_test.uri.get_path())

    def test_parse_db_line_admin_dirs(self):
        admin_dirs = ["/adm/", "/admin/"]

        config = Config(["/cgi-bin/"], admin_dirs, [], [], [])
        url = URL("http://moth/")
        pykto_inst = self.pykto_inst
        nikto_parser = NiktoTestParser(pykto_inst._db_file, config, url)

        line = '"0","0","","@ADMIN","GET","200"' ',"","","","","","",""'
        nikto_tests = [i for i in nikto_parser._parse_db_line(line)]

        self.assertEqual(len(nikto_tests), 2)

        self.assertEqual(admin_dirs, [nt.uri.get_path() for nt in nikto_tests])

    def test_parse_db_line_admin_users_two(self):
        admin_dirs = ["/adm/", "/admin/"]
        users = ["sys", "root"]

        config = Config([], admin_dirs, [], [], users)
        url = URL("http://moth/")
        pykto_inst = self.pykto_inst
        nikto_parser = NiktoTestParser(pykto_inst._db_file, config, url)

        line = '"0","0","","@ADMIN@USERS","GET","200"' ',"","","","","","",""'
        nikto_tests = [i for i in nikto_parser._parse_db_line(line)]

        self.assertEqual(len(nikto_tests), 4)

        self.assertEqual(
            ["/adm/sys", "/adm/root", "/admin/sys", "/admin/root"],
            [nt.uri.get_path() for nt in nikto_tests],
        )

    def test_parse_db_line_non_ascii(self):
        config = Config(["/cgi-bin/"], [], [], [], [])
        url = URL("http://moth/")
        nikto_parser = NiktoTestParser(self.pykto_inst._db_file, config, url)

        line = (
            '"006251","0","1","/administraçao.php","GET","200","","",""'
            ',"","Admin login page/section found.","",""'
        )
        nikto_tests = list(nikto_parser._parse_db_line(line))

        self.assertEqual(len(nikto_tests), 1)
        self.assertEqual(nikto_tests[0].message, "Admin login page/section found.")

    def test_parse_db_line_ignores_invalid_lines(self):
        config = Config([], [], [], [], [])
        url = URL("http://moth/")
        nikto_parser = NiktoTestParser(self.pykto_inst._db_file, config, url)

        short_line = '"0","0","","/docs/","GET","200"'
        space_line = '"0","0","","/a b/","GET","200","","","","","","",""'
        bad_regex_line = '"0","0","","/docs/","GET","(unclosed","","","","","","",""'

        for line in (short_line, space_line, bad_regex_line):
            self.assertEqual(list(nikto_parser._parse_db_line(line)), [], line)

        self.assertEqual(nikto_parser.ignored, [short_line, space_line])

    def test_parse_db_line_regex_and_status_matchers(self):
        config = Config([], [], [], [], [])
        url = URL("http://moth/")
        nikto_parser = NiktoTestParser(self.pykto_inst._db_file, config, url)

        line = '"0","0","","/docs/","GET","Index of","302","","500","","Docs\r\n","",""'
        (nikto_test,) = nikto_parser._parse_db_line(line)

        self.assertEqual(nikto_test.match_1.pattern, "Index of")
        self.assertEqual(nikto_test.match_1_or, 302)
        self.assertEqual(nikto_test.fail_1, 500)
        self.assertEqual(nikto_test.message, "Docs")

    def test_missing_scan_database(self):
        config = Config([], [], [], [], [])
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_db = os.path.join(temp_dir, "missing.db")
            nikto_parser = NiktoTestParser(missing_db, config, URL("http://moth/"))

            self.assertEqual(list(nikto_parser.test_generator()), [])

    def test_parse_db_line_basic_w3af_scan_database(self):
        """
        This test reads a line from the w3af scan database and parses it, it's
        objective is to make sure that we can read both formats (or better yet,
        that both files: the one from nikto and the one we have are in the same
        format).

        https://github.com/andresriancho/w3af/issues/317
        """
        config = Config([], [], [], [], [])
        url = URL("http://moth/")
        pykto_inst = self.pykto_inst
        nikto_parser = NiktoTestParser(pykto_inst._extra_db_file, config, url)

        # Go through all the lines
        generator = nikto_parser.test_generator()
        nikto_tests = [i for (i,) in generator]

        self.assertLess(len(nikto_parser.ignored), 30, len(nikto_parser.ignored))

        self.assertEqual(len(nikto_tests), 3)

        nikto_test = nikto_tests[0]

        self.assertEqual(nikto_test.id, "900001")
        self.assertEqual(nikto_test.osvdb, "0")
        self.assertEqual(nikto_test.tune, "3")
        self.assertEqual(nikto_test.uri.url_string, "http://moth/debug.seam")
        self.assertEqual(nikto_test.method, "GET")
        self.assertIsInstance(nikto_test.match_1, type(re.compile("")))
        self.assertEqual(nikto_test.match_1_or, None)
        self.assertEqual(nikto_test.match_1_and, None)
        self.assertEqual(nikto_test.fail_1, None)
        self.assertEqual(nikto_test.fail_2, None)
        self.assertEqual(nikto_test.message, "JBoss Seam Debug Page is available.")
        self.assertEqual(nikto_test.data, "")
        self.assertEqual(nikto_test.headers, "")


class TestPyktoOptions(unittest.TestCase):

    def test_set_options(self):
        plugin = pykto()

        options = plugin.get_options()
        options["cgi_dirs"].set_value("/cgi/")
        options["admin_dirs"].set_value("/administrator/")
        options["nuke_dirs"].set_value("/nuke/")
        options["db_file"].set_value(DB_PATH)
        options["mutate_tests"].set_value(True)
        plugin.set_options(options)

        options = plugin.get_options()
        self.assertEqual(options["cgi_dirs"].get_value(), ["/cgi/"])
        self.assertEqual(options["admin_dirs"].get_value(), ["/administrator/"])
        self.assertEqual(options["nuke_dirs"].get_value(), ["/nuke/"])
        self.assertTrue(os.path.samefile(options["db_file"].get_value(), DB_PATH))
        self.assertTrue(options["mutate_tests"].get_value())


class TestPyktoRunOnce(unittest.TestCase):

    def test_second_crawl_without_mutation_raises_run_once(self):
        worker_pool = Pool(1, worker_names="PyktoWorker")
        self.addCleanup(worker_pool.terminate_join)

        with tempfile.NamedTemporaryFile("w", suffix=".db", delete=False) as empty_db:
            empty_db.write("# no tests\n")
        self.addCleanup(os.remove, empty_db.name)

        plugin = pykto()
        plugin.set_worker_pool(worker_pool)
        options = plugin.get_options()
        options["db_file"].set_value(empty_db.name)
        options["extra_db_file"].set_value(empty_db.name)
        plugin.set_options(options)

        fuzzable_request = FuzzableRequest(URL("http://mock/w3af/"))
        plugin.crawl(fuzzable_request, None)

        self.assertRaises(RunOnce, plugin.crawl, fuzzable_request, None)
