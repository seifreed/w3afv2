"""
test_deserialization.py

Copyright 2018 Andres Riancho

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

import base64
import binascii
import importlib
import json
import os
import re
import time
import unittest
import urllib.parse
from pathlib import Path
from typing import ClassVar

from w3af.core.data.dc.cookie import Cookie
from w3af.core.data.dc.urlencoded_form import URLEncodedForm
from w3af.core.data.fuzzer.mutants.cookie_mutant import CookieMutant
from w3af.core.data.fuzzer.mutants.postdata_mutant import PostDataMutant
from w3af.core.data.fuzzer.mutants.querystring_mutant import QSMutant
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.utils.form_params import FormParameters
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.audit.deserialization import (
    B64DeserializationExactDelay,
    DeserializationExactDelay,
    deserialization,
)
from w3af.plugins.tests.audit.vulnerable_responses import html_page, request_param
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

_pickletools = importlib.import_module("pickletools")

test_config = {
    "audit": (PluginConfig("deserialization"),),
}

DESERIALIZE_URL = "http://mock/deserialize"

SERIALIZED_INT = "I1\n."
SERIALIZED_DICT = (
    "(dp0\nS'data'\np1\nS'here'\np2\nsS'cookie'\np3\nS'AAAAAAAAAAAAAAAA'\np4\ns."
)


def emulate_deserialization(data):
    """
    Emulate the side effects of deserializing data without running any code:
    the opcodes are disassembled and the only callable honoured is time.sleep,
    which is the one the w3af payloads use.

    :raise ValueError: When data is not a valid serialized object
    """
    opcodes = [(opcode.name, arg) for opcode, arg, _ in _pickletools.genops(data)]
    if ("GLOBAL", "time sleep") in opcodes:
        seconds = next(arg for name, arg in opcodes if name == "INT")
        time.sleep(seconds)


def deserialize_response(response_headers, message):
    try:
        emulate_deserialization(message)
    except ValueError as error:
        return html_page(response_headers, str(error))
    return html_page(response_headers, "Message received")


def b64_site(mock_response, request, uri, response_headers):
    """Deserialize the base64 decoded message parameter."""
    try:
        message = base64.b64decode(request_param(request, "message"))
    except binascii.Error as error:
        return html_page(response_headers, str(error))
    return deserialize_response(response_headers, message)


def raw_site(mock_response, request, uri, response_headers):
    """Deserialize the message parameter."""
    message = request_param(request, "message").encode("latin-1")
    return deserialize_response(response_headers, message)


def b64(data):
    return base64.b64encode(data.encode("latin-1")).decode("ascii")


class TestDeserializePickle(PluginTest):

    target_url = f"{DESERIALIZE_URL}?message="

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{DESERIALIZE_URL}.*"), b64_site),
    ]

    def test_found_deserialization_in_pickle(self):
        self._scan(self.target_url, test_config)

        vulns = self.kb.get("deserialization", "deserialization")

        self.assertEqual(1, len(vulns), vulns)

        vuln = vulns[0]
        self.assertEqual("message", vuln.get_token_name())
        self.assertEqual("Insecure deserialization", vuln.get_name())


class TestDeserializePickleNotBase64(PluginTest):

    target_url = f"{DESERIALIZE_URL}?message="

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{DESERIALIZE_URL}.*"), raw_site),
    ]

    def test_found_deserialization_in_pickle(self):
        self._scan(self.target_url, test_config)

        vulns = self.kb.get("deserialization", "deserialization")

        self.assertEqual(1, len(vulns), vulns)

        vuln = vulns[0]
        self.assertEqual("message", vuln.get_token_name())
        self.assertEqual("Insecure deserialization", vuln.get_name())


class TestShouldInjectIsCalled(PluginTest):

    target_url = f"{DESERIALIZE_URL}?message=this-disables-injection"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{DESERIALIZE_URL}.*"), b64_site),
    ]

    def test_found_deserialization_in_pickle(self):
        self._scan(self.target_url, test_config)

        vulns = self.kb.get("deserialization", "deserialization")

        self.assertEqual(0, len(vulns), vulns)


class TestRawExactDelay(unittest.TestCase):
    def test_get_payload_sets_the_delay_digits(self):
        payload = {
            "1": {
                "payload": base64.b64encode(b"ctime\nsleep\n(I1\ntR.").decode(),
                "offsets": [14],
            },
            "2": {
                "payload": base64.b64encode(b"ctime\nsleep\n(I22\ntR.").decode(),
                "offsets": [14],
            },
        }
        delay = DeserializationExactDelay(payload)

        self.assertEqual("ctime\nsleep\n(I7\ntR.", delay.get_string_for_delay(7))
        self.assertEqual("ctime\nsleep\n(I35\ntR.", delay.get_string_for_delay(35))


class TestShouldInject(unittest.TestCase):
    def setUp(self):
        self.plugin = deserialization()
        self.payloads = [""]
        self.fuzzer_config = {"fuzz_cookies": True}

    def test_should_inject_empty_qs(self):
        self.url = URL("http://moth/?id=")
        freq = FuzzableRequest(self.url)

        mutant = QSMutant.create_mutants(
            freq, self.payloads, [], False, self.fuzzer_config
        )[0]

        self.assertTrue(self.plugin._should_inject(mutant, "python"))

    def test_should_not_inject_qs_with_digit(self):
        self.url = URL("http://moth/?id=1")
        freq = FuzzableRequest(self.url)

        mutant = QSMutant.create_mutants(
            freq, self.payloads, [], False, self.fuzzer_config
        )[0]

        self.assertFalse(self.plugin._should_inject(mutant, "python"))

    def test_should_not_inject_qs_with_b64(self):
        b64data = b64("just some random b64 data here")
        self.url = URL(f"http://moth/?id={b64data}")
        freq = FuzzableRequest(self.url)

        mutant = QSMutant.create_mutants(
            freq, self.payloads, [], False, self.fuzzer_config
        )[0]

        self.assertFalse(self.plugin._should_inject(mutant, "python"))

    def test_should_inject_qs_with_b64_pickle(self):
        b64data = b64(SERIALIZED_DICT)
        self.url = URL(f"http://moth/?id={b64data}")
        freq = FuzzableRequest(self.url)

        mutant = QSMutant.create_mutants(
            freq, self.payloads, [], False, self.fuzzer_config
        )[0]

        self.assertTrue(self.plugin._should_inject(mutant, "python"))

    def test_should_not_inject_qs_with_b64_pickle_java(self):
        b64data = b64(SERIALIZED_INT)
        self.url = URL(f"http://moth/?id={b64data}")
        freq = FuzzableRequest(self.url)

        mutant = QSMutant.create_mutants(
            freq, self.payloads, [], False, self.fuzzer_config
        )[0]

        self.assertFalse(self.plugin._should_inject(mutant, "java"))

    def test_should_inject_qs_with_pickle(self):
        pickle_data = urllib.parse.quote(SERIALIZED_INT)
        self.url = URL(f"http://moth/?id={pickle_data}")
        freq = FuzzableRequest(self.url)

        mutant = QSMutant.create_mutants(
            freq, self.payloads, [], False, self.fuzzer_config
        )[0]

        self.assertTrue(self.plugin._should_inject(mutant, "python"))

    def test_should_inject_form_hidden(self):
        form_params = FormParameters()
        form_params.add_field_by_attr_items([("name", "username"), ("type", "text")])
        form_params.add_field_by_attr_items(
            [("name", "csrf_token"), ("type", "hidden")]
        )

        form = URLEncodedForm(form_params)
        freq = FuzzableRequest(
            URL("http://www.w3af.com/"), post_data=form, method="PUT"
        )
        m = PostDataMutant(freq)
        m.get_dc().set_token(("username", 0))

        self.assertFalse(self.plugin._should_inject(m, "python"))

        m.get_dc().set_token(("csrf_token", 0))
        self.assertTrue(self.plugin._should_inject(m, "python"))

    def test_should_inject_cookie_value(self):
        b64data = b64(SERIALIZED_DICT)

        url = URL("http://moth/")
        cookie = Cookie(f"foo={b64data}")
        freq = FuzzableRequest(url, cookie=cookie)

        mutant = CookieMutant.create_mutants(
            freq, self.payloads, [], False, self.fuzzer_config
        )[0]

        self.assertTrue(self.plugin._should_inject(mutant, "python"))

    def test_should_not_inject_random_binary(self):
        self.url = URL("http://moth/?id={}".format("\x00\x01\x02"))
        freq = FuzzableRequest(self.url)

        mutant = QSMutant.create_mutants(
            freq, self.payloads, [], False, self.fuzzer_config
        )[0]

        self.assertFalse(self.plugin._should_inject(mutant, "java"))


class TestJSONPayloadIsValid(unittest.TestCase):
    def test_all_jsons_are_valid(self):
        loaded_payloads = 0

        for root, dirs, files in os.walk(deserialization.PAYLOADS):

            # Ignore helpers used for creating the nodejs payloads
            if "node_modules" in root:
                continue

            for file_name in files:

                # Ignore helpers used for creating the nodejs payloads
                if file_name in ("package-lock.json", "package.json"):
                    continue

                if file_name.endswith(deserialization.PAYLOAD_EXTENSION):
                    json_str = Path(os.path.join(root, file_name)).read_text()
                    data = json.loads(json_str)

                    self.assertIn("1", data, file_name)
                    self.assertIn("2", data, file_name)

                    self.assertIn("payload", data["1"], file_name)
                    self.assertIn("offsets", data["1"], file_name)

                    self.assertIn("payload", data["2"], file_name)
                    self.assertIn("offsets", data["2"], file_name)

                    self.assertGreater(len(data["1"]["offsets"]), 0)
                    self.assertGreater(len(data["2"]["offsets"]), 0)

                    for delay_len in [1, 2]:
                        for offset in data[str(delay_len)]["offsets"]:
                            self.assertIsInstance(offset, int, file_name)

                            payload = base64.b64decode(data[str(delay_len)]["payload"])
                            self.assertGreater(len(payload), offset, file_name)

                    loaded_payloads += 1

        self.assertGreater(loaded_payloads, 0)


class TestExactDelay(unittest.TestCase):
    def test_get_payload(self):
        payload = {
            "1": {
                "payload": "Y3RpbWUKc2xlZXAKcDEKKEkxCnRwMgpScDMKLg==",
                "offsets": [17],
            },
            "2": {
                "payload": "Y3RpbWUKc2xlZXAKcDEKKEkyMgp0cDIKUnAzCi4=",
                "offsets": [17],
            },
        }

        ed = B64DeserializationExactDelay(payload)

        payload_1 = ed.get_string_for_delay(1)
        payload_22 = ed.get_string_for_delay(22)

        self.assertEqual(payload["1"]["payload"], payload_1)
        self.assertEqual(payload["2"]["payload"], payload_22)

    def test_get_payload_all(self):
        for root, dirs, files in os.walk(deserialization.PAYLOADS):

            # Ignore helpers used for creating the nodejs payloads
            if "node_modules" in root:
                continue

            for file_name in files:

                # Ignore helpers used for creating the nodejs payloads
                if file_name in ("package-lock.json", "package.json"):
                    continue

                if file_name.endswith(deserialization.PAYLOAD_EXTENSION):
                    json_str = Path(os.path.join(root, file_name)).read_text()
                    payload = json.loads(json_str)

                    ed = B64DeserializationExactDelay(payload)

                    try:
                        payload_1 = ed.get_string_for_delay(1)
                        payload_22 = ed.get_string_for_delay(22)
                    except (TypeError, ValueError, KeyError) as e:
                        msg = 'Raised exception "%s" on "%s"'
                        args = (e, file_name)
                        self.assertTrue(False, msg % args)

                    # file('1', 'w').write(base64.b64decode(payload['1']['payload']))
                    # file('2', 'w').write(base64.b64decode(payload_1))

                    self.assertEqual(payload["1"]["payload"], payload_1, file_name)
                    self.assertEqual(payload["2"]["payload"], payload_22, file_name)
