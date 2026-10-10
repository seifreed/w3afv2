"""
test_strategy.py

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

import io
import re
import time
import unittest
from contextlib import redirect_stdout
from urllib.parse import parse_qs, unquote_plus, urlsplit

import pytest

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.controllers.misc.factory import factory
from w3af.core.controllers.tests.grep_exception_raise import GrepFailureError
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.kb.config import Config
from w3af.core.data.parsers.doc.url import URL
from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.plugins.tests.helper import (
    PluginConfig,
    PluginTest,
    create_target_option_list,
)
from w3af.tests.helpers.sqli_site import STRING_QS, SQLInjectionSite

XSS_INDEX = """<html><body>
<a href="greeting.py?name=pablo">Greeting</a>
<a href="search.py?text=w3af">Search</a>
<a href="safe.py?id=1">Safe</a>
</body></html>"""

VULN_STRING = "A Cross Site Scripting vulnerability was found at"
URL_VULN_RE = re.compile(f'{VULN_STRING}: "(.*?)"')


def query_value(path):
    query = parse_qs(urlsplit(path).query, keep_blank_values=True)
    return unquote_plus(next(iter(query.values()), [""])[0])


def xss_site(method, path):
    """
    A web application which reflects the user input without encoding it in
    two different HTML contexts.
    """
    page = urlsplit(path).path
    value = query_value(path)

    if page == "/":
        return Reply(body=XSS_INDEX)
    if page == "/greeting.py":
        return Reply(body=f"<html><body>Hello {value}</body></html>")
    if page == "/search.py":
        return Reply(body=f'<html><body><input value="{value}"></body></html>')
    if page == "/safe.py":
        return Reply(body="<html><body>Nothing to see</body></html>")
    return Reply(status=404, body="Not found")


def endless_site(method, path):
    """
    Every page links to two new pages and takes a while to answer, crawling
    this site never ends.
    """
    time.sleep(0.3)
    page = urlsplit(path).path.strip("/")
    number = int(page) if page.isdigit() else 0
    links = "".join(f'<a href="/{number * 2 + i}">{i}</a>' for i in (1, 2))
    return Reply(body=f"<html><body>{links}</body></html>")


class LoginSite:
    """
    Every page greets the user after the login form was submitted. The pages
    are slow, which keeps the crawl busy while the other consumers are idle.
    """

    def __init__(self):
        self.logged_in = False

    def __call__(self, method, path):
        if method == "POST" and path == "/login":
            self.logged_in = True

        time.sleep(0.3)
        greeting = "Welcome" if self.logged_in else "Please login"
        links = "".join(f'<a href="/{page}">{page}</a>' for page in "abc")
        return Reply(body=f"<html><body>{greeting} {links}</body></html>")


class TestDeterministicResults(unittest.TestCase):
    """
    Pseudo-random number of vulnerabilities found in audit phase (xss)

    https://github.com/andresriancho/w3af/issues/1557
    """

    def setUp(self):
        kb.kb.cleanup()
        self.site = LocalHTTPServer(xss_site).start()
        self.addCleanup(self.site.close)

    def scan_commands(self):
        return [
            "plugins",
            "audit xss",
            "crawl web_spider",
            "crawl config web_spider",
            "set only_forward True",
            "back",
            "back",
            "target",
            f"set target {self.site.url('/')}",
            "back",
            "start",
            "exit",
        ]

    def found_vulnerable_urls(self):
        console = ConsoleUI(commands=self.scan_commands(), do_upd=False)
        output = io.StringIO()

        with redirect_stdout(output):
            console.sh()

        return {
            URL_VULN_RE.search(line).group(1)
            for line in output.getvalue().splitlines()
            if VULN_STRING in line
        }

    def test_1557_same_results_in_every_scan(self):
        first_scan = self.found_vulnerable_urls()
        kb.kb.cleanup()
        second_scan = self.found_vulnerable_urls()

        expected = {
            self.site.url("/greeting.py"),
            self.site.url("/search.py"),
        }
        self.assertEqual(first_scan, expected)
        self.assertEqual(second_scan, first_scan)


class TestSameFuzzableRequestSet(PluginTest):
    @pytest.mark.smoke
    def test_same_fr_set_object(self):
        site = SQLInjectionSite.serve_for(self)
        target = f"{site.url}{STRING_QS}?uname=pablo"
        plugins = {"audit": (PluginConfig("sqli"),)}

        id_before_fr = id(self.kb.get_all_known_fuzzable_requests())
        id_before_ur = id(self.kb.get_all_known_urls())

        self._scan(target, plugins)

        id_after_fr = id(self.kb.get_all_known_fuzzable_requests())
        id_after_ur = id(self.kb.get_all_known_urls())

        self.assertEqual(id_before_fr, id_after_fr)
        self.assertEqual(id_before_ur, id_after_ur)


class TestScanConsumers(unittest.TestCase):
    """
    Run complete scans with every consumer type enabled
    """

    def setUp(self):
        kb.kb.cleanup()
        self.max_scan_time = cf.get("max_scan_time")
        self.addCleanup(cf.save, "max_scan_time", self.max_scan_time)

        self.core = w3afCore(configuration=cf)
        self.addCleanup(self.core.quit)

    def start_scan(self, responder, plugins):
        server = LocalHTTPServer(responder).start()
        self.addCleanup(server.close)

        target_opts = create_target_option_list(URL(server.url("/")))
        self.core.target.set_options(target_opts)

        for plugin_type, plugin_names in plugins.items():
            self.core.plugins.set_plugins(plugin_names, plugin_type)

        if "generic" in plugins.get("auth", []):
            self.configure_generic_auth(server.url)

        self.core.plugins.init_plugins()
        self.recorder = start_recording_output()

    def configure_generic_auth(self, server_url):
        options = self.core.plugins.get_plugin_inst("auth", "generic").get_options()
        auth_value = "xy"
        field_name = "field"
        values = {
            "username": "operator",
            "password": auth_value,
            "username_field": "user",
            "password_field": field_name,
            "auth_url": server_url("/login"),
            "check_url": server_url("/"),
            "check_string": "Welcome",
        }
        for name, value in values.items():
            options[name].set_value(value)
        self.core.plugins.set_plugin_options("auth", "generic", options)

    def add_grep_plugin(self, module_name):
        plugin_inst = factory(module_name)
        plugin_inst.set_url_opener(self.core.uri_opener)
        plugin_inst.set_worker_pool(self.core.worker_pool)
        self.core.plugins.plugins["grep"] = [plugin_inst]
        self.core.plugins._plugins_names_dict["grep"] = [plugin_inst.get_name()]

    def test_grep_auth_and_bruteforce_consumers(self):
        cf.save("max_scan_time", 0)

        self.start_scan(
            LoginSite(),
            {
                "crawl": ["web_spider"],
                "auth": ["generic"],
                "bruteforce": ["basic_auth"],
            },
        )
        self.add_grep_plugin("w3af.core.controllers.tests.grep_exception_raise")

        self.core.verify_environment()
        self.core.start()

        exceptions = self.core.exception_handler.get_all_exceptions()
        self.assertTrue(exceptions)
        self.assertEqual(
            {e.get_exception_class() for e in exceptions},
            {GrepFailureError.__name__},
        )
        self.assertEqual({e.phase for e in exceptions}, {"grep"})
        self.assertEqual(kb.kb.get("authentication", "error"), [])

    def test_scan_stops_at_max_scan_time(self):
        cf.save("max_scan_time", 0.02)

        self.start_scan(endless_site, {"crawl": ["web_spider"]})

        self.core.verify_environment()
        self.core.start()

        messages = " ".join(self.recorder.messages_of("information"))
        self.assertIn("The scan has reached the maximum scan time of 0.02", messages)


cf = Config()
