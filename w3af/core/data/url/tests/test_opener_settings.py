"""
test_opener_settings.py

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
import tempfile
import unittest

from w3af.core.data.kb.config import cf
from w3af.core.data.options.option_types import (
    BOOL,
    COMBO,
    FLOAT,
    INPUT_FILE,
    INT,
    IPPORT,
    LIST,
    OUTPUT_FILE,
    PORT,
    POSITIVE_INT,
    REGEX,
    STRING,
    URL,
    URL_LIST,
)
from w3af.core.data.parsers.doc.url import URL as URLParser
from w3af.core.data.url.opener_settings import OpenerSettings
from w3af.core.exceptions import BaseFrameworkException

OPTION_TYPES = (
    BOOL,
    INT,
    POSITIVE_INT,
    FLOAT,
    STRING,
    URL,
    IPPORT,
    LIST,
    REGEX,
    COMBO,
    INPUT_FILE,
    OUTPUT_FILE,
    PORT,
    URL_LIST,
)


class TestOpenerSettings(unittest.TestCase):

    def setUp(self):
        self.os = OpenerSettings(configuration=cf)

    def test_options(self):
        opt_lst = self.os.get_options()
        self.os.set_options(opt_lst)

        for opt in opt_lst:
            self.assertIn(opt.get_type(), OPTION_TYPES)
            self.assertTrue(opt.get_name())
            self.assertEqual(opt, opt)

            # Just verify that this doesn't crash and that the types
            # are correct
            self.assertIsInstance(opt.get_name(), str)
            self.assertIsInstance(opt.get_desc(), str)
            self.assertIsInstance(opt.get_type(), str)
            self.assertIsInstance(opt.get_help(), str)
            self.assertIsInstance(opt.get_value_str(), str)

    def test_desc(self):
        self.os.get_desc()


COOKIE_JAR = (
    "# Netscape HTTP Cookie File\n"
    "127.0.0.1\tFALSE\t/\tFALSE\t2736616305\tsession\t123456789\n"
)


class TestOpenerSettingsConfiguration(unittest.TestCase):

    def setUp(self):
        self.settings = OpenerSettings(configuration=cf)
        self.addCleanup(self.settings.set_default_values)

    def write_file(self, contents):
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp_file:
            tmp_file.write(contents)

        self.addCleanup(os.unlink, tmp_file.name)
        return tmp_file.name

    def test_headers_file(self):
        self.settings.set_headers_file("")
        self.assertEqual(cf.get("headers_file"), "")

        headers_file = self.write_file("X-Api-Key: secret\nX-Time: 10:20\n")
        self.settings.set_headers_file(headers_file)

        self.assertIn(("X-Api-Key", "secret"), self.settings.header_list)
        self.assertIn(("X-Time", "10:20"), self.settings.header_list)
        self.assertEqual(cf.get("headers_file"), headers_file)

    def test_headers_file_does_not_exist(self):
        self.assertRaises(
            BaseFrameworkException,
            self.settings.set_headers_file,
            "/does/not/exist/headers.txt",
        )

    def test_cookie_jar_file(self):
        self.settings.set_cookie_jar_file("")
        self.assertEqual(cf.get("cookie_jar_file"), "")

        cookie_jar = self.write_file(COOKIE_JAR)
        self.settings.set_cookie_jar_file(cookie_jar)

        cookies = list(self.settings.get_cookies())
        self.assertEqual(
            [(c.name, c.value) for c in cookies], [("session", "123456789")]
        )
        self.assertEqual(cf.get("cookie_jar_file"), cookie_jar)

        self.settings.clear_cookies()
        self.assertEqual(list(self.settings.get_cookies()), [])

    def assert_cookie_jar_error(self, contents, message):
        cookie_jar = self.write_file(contents)

        with self.assertRaises(BaseFrameworkException) as raised:
            self.settings.set_cookie_jar_file(cookie_jar)

        self.assertIn(message, str(raised.exception))

    def test_cookie_jar_file_without_cookies(self):
        self.assert_cookie_jar_error(
            "# Netscape HTTP Cookie File\n", "Did not load any cookies"
        )

    def test_cookie_jar_file_invalid_format(self):
        self.assert_cookie_jar_error(
            "# Netscape HTTP Cookie File\n"
            "127.0.0.1\tFALSE\t/\tFALSE\tnot-a-number\tsession\t1\n",
            "is not in Netscape format",
        )

    def test_cookie_jar_file_load_error(self):
        self.assert_cookie_jar_error("not a cookie jar\n", "Error while loading")

    def test_cookie_jar_file_does_not_exist(self):
        with self.assertRaises(BaseFrameworkException) as raised:
            self.settings.set_cookie_jar_file("/does/not/exist/cookies.txt")

        self.assertIn("does not exist", str(raised.exception))

    def test_configured_timeout(self):
        self.settings.set_configured_timeout(10)
        self.assertEqual(self.settings.get_configured_timeout(), 10)

        for invalid in (-1, 31):
            self.assertRaises(
                BaseFrameworkException, self.settings.set_configured_timeout, invalid
            )

    def test_set_user_agent_replaces_the_previous_one(self):
        self.settings.set_user_agent("first")
        self.settings.set_user_agent("second")

        user_agents = [v for h, v in self.settings.header_list if h == "User-Agent"]
        self.assertEqual(user_agents, ["second"])
        self.assertEqual(cf.get("user_agent"), "second")

    def test_rand_user_agent(self):
        self.settings.set_rand_user_agent(True)

        self.assertTrue(self.settings.rand_user_agent)
        self.assertTrue(cf.get("rand_user_agent"))

    def test_proxy(self):
        self.settings.set_proxy("127.0.0.1", 3128)
        self.assertEqual(self.settings.get_proxy(), "127.0.0.1:3128")
        self.assertIsNotNone(self.settings._proxy_handler)

        self.settings.set_proxy("", 3128)
        self.assertEqual(self.settings.get_proxy(), ":3128")
        self.assertIsNone(self.settings._proxy_handler)

    def test_proxy_invalid_port(self):
        for port in (0, 65536):
            self.assertRaises(
                BaseFrameworkException, self.settings.set_proxy, "127.0.0.1", port
            )
            self.assertIsNone(self.settings._proxy_handler)

    def test_basic_auth(self):
        url = URLParser("http://w3af.org/")
        self.settings.set_basic_auth(url, "user", "pass")

        self.assertEqual(
            self.settings._password_mgr.find_user_password(None, "w3af.org"),
            ("user", "pass"),
        )
        self.assertEqual(cf.get("basic_auth_user"), "user")
        self.assertTrue(self.settings.need_update)

    def test_basic_auth_invalid_domain(self):
        self.assertRaises(
            BaseFrameworkException, self.settings.set_basic_auth, None, "u", "p"
        )

    def test_basic_auth_credentials_without_domain(self):
        self.assertRaises(
            BaseFrameworkException, self.settings.set_basic_auth, "", "u", "p"
        )

    def test_basic_auth_cleared(self):
        self.settings.set_basic_auth("", "", "")

        self.assertIsNone(self.settings._basic_auth_handler)
        self.assertEqual(cf.get("basic_auth_domain"), "")

    def test_ntlm_auth(self):
        self.settings.set_ntlm_auth("http://w3af.org/", "DOMAIN", "user", "pass")

        self.assertEqual(
            self.settings._password_mgr.find_user_password(None, "http://w3af.org/"),
            ("DOMAIN\\user", "pass"),
        )
        self.assertIsNotNone(self.settings._ntlm_auth_handler)
        self.assertEqual(cf.get("ntlm_auth_domain"), "DOMAIN")

    def handler_names(self):
        self.settings.build_openers()
        opener = self.settings.get_custom_opener()
        return {type(handler).__name__ for handler in opener.handlers}

    def test_build_openers(self):
        self.settings.set_mangle_plugins([])
        names = self.handler_names()

        self.assertIn("CookieHandler", names)
        self.assertNotIn("HTTPLogHandler", names)
        self.assertNotIn("URLParameterHandler", names)
        self.assertEqual(
            self.settings.get_custom_opener().addheaders, [("Accept", "*/*")]
        )

    def test_build_openers_ignoring_session_cookies(self):
        cf.save("ignore_session_cookies", True)

        self.assertNotIn("CookieHandler", self.handler_names())

    def test_build_openers_with_log_callback(self):
        self.settings = OpenerSettings(http_log_callback=print, configuration=cf)

        self.assertIn("HTTPLogHandler", self.handler_names())

    def test_url_parameter(self):
        self.settings.set_url_parameter("   ")
        self.assertEqual(cf.get("url_parameter"), "")

        self.settings.set_url_parameter(" 'jsessionid=1' ")
        self.assertEqual(cf.get("url_parameter"), "jsessionid=1")
        self.assertIn("URLParameterHandler", self.handler_names())

    def test_clear_cache(self):
        self.assertTrue(self.settings.clear_cache())

        self.settings.build_openers()
        self.assertTrue(self.settings.clear_cache())

    def test_set_options_invalid_basic_auth_domain(self):
        options = self.settings.get_options()
        options["basic_auth_domain"].set_value("http://[invalid")
        options["basic_auth_user"].set_value("user")

        self.assertRaises(BaseFrameworkException, self.settings.set_options, options)

    def test_set_options_applies_changes(self):
        options = self.settings.get_options()
        options["basic_auth_domain"].set_value("http://w3af.org/")
        options["basic_auth_user"].set_value("user")
        options["basic_auth_passwd"].set_value("pass")
        options["proxy_address"].set_value("127.0.0.1")
        options["proxy_port"].set_value(3128)
        options["url_parameter"].set_value("sid=1")

        self.settings.set_options(options)

        self.assertEqual(cf.get("basic_auth_domain"), URLParser("http://w3af.org/"))
        self.assertEqual(self.settings.get_proxy(), "127.0.0.1:3128")
        self.assertEqual(cf.get("url_parameter"), "sid=1")
