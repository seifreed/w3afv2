"""Validation and fallback paths of the data containers."""

import copy
import datetime
import json
import unittest

from w3af.core.data.dc.cookie import Cookie
from w3af.core.data.dc.factory import (
    dc_from_content_type_and_raw_params,
    dc_from_hdrs_post,
)
from w3af.core.data.dc.generic.data_container import DataContainer
from w3af.core.data.dc.generic.kv_container import KeyValueContainer
from w3af.core.data.dc.generic.nr_kv_container import NonRepeatKeyValueContainer
from w3af.core.data.dc.generic.plain import PlainContainer
from w3af.core.data.dc.headers import Headers
from w3af.core.data.dc.json_container import JSONContainer
from w3af.core.data.dc.multipart_container import MultipartContainer
from w3af.core.data.dc.query_string import QueryString
from w3af.core.data.dc.urlencoded_form import URLEncodedForm
from w3af.core.data.dc.utils.file_token import FileDataToken
from w3af.core.data.dc.utils.json_encoder import DateTimeJSONEncoder
from w3af.core.data.dc.utils.multipart import _split_vars_files
from w3af.core.data.dc.utils.token import DataToken
from w3af.core.data.dc.xmlrpc import XmlRpcContainer
from w3af.core.data.misc.io import NamedStringIO
from w3af.core.data.parsers.utils.form_params import FormParameters

LONG_VALUE = "x" * 100


class TestTypeNames(unittest.TestCase):
    def test_get_type(self):
        self.assertEqual(Cookie().get_type(), "Cookie")
        self.assertEqual(Headers().get_type(), "Headers")
        self.assertEqual(DataContainer().get_type(), "Generic data container")
        self.assertEqual(KeyValueContainer().get_type(), "Generic key value container")
        self.assertEqual(
            NonRepeatKeyValueContainer().get_type(),
            "Generic non-repeat key value container",
        )
        self.assertEqual(JSONContainer("{}").get_type(), "JSON")
        self.assertEqual(MultipartContainer().get_type(), "Multipart/post")


class TestDataContainerContract(unittest.TestCase):
    def test_abstract_methods(self):
        container = DataContainer()

        self.assertRaises(
            NotImplementedError, DataContainer.from_postdata, Headers(), ""
        )
        self.assertRaises(NotImplementedError, container.get_short_printable_repr)
        self.assertRaises(NotImplementedError, str, container)

    def test_no_extra_headers_by_default(self):
        self.assertEqual(KeyValueContainer().get_headers(), [])

    def test_set_token_lists_valid_paths(self):
        container = KeyValueContainer([("a", ["1"])])

        with self.assertRaisesRegex(RuntimeError, "Valid paths are"):
            container.set_token(("b", 0))


class TestKeyValueContainerValidation(unittest.TestCase):
    def test_copy_constructor(self):
        original = KeyValueContainer([("a", ["1"])])

        self.assertEqual(KeyValueContainer(original), original)

    def test_invalid_init_values(self):
        for init_val in (
            {"a": ["1"]},
            [1],
            [("a", ["1"]), ("a", ["2"])],
            [("a", "1")],
            [("a", [1])],
        ):
            with self.subTest(init_val=init_val):
                self.assertRaises(TypeError, KeyValueContainer, init_val)


class TestNonRepeatKeyValueContainer(unittest.TestCase):
    def test_invalid_init_values(self):
        for init_val in ([1], [("a", 1)]):
            with self.subTest(init_val=init_val):
                self.assertRaises(TypeError, NonRepeatKeyValueContainer, init_val)

    def test_short_printable_repr_long_value(self):
        container = NonRepeatKeyValueContainer([("a", LONG_VALUE)])

        self.assertEqual(
            container.get_short_printable_repr(),
            f"a={LONG_VALUE}"[: container.MAX_PRINTABLE],
        )

    def test_short_printable_repr_long_value_with_token(self):
        container = NonRepeatKeyValueContainer([("b", "1"), ("a", LONG_VALUE)])
        container.set_token(("a",))

        self.assertEqual(
            container.get_short_printable_repr(),
            f"...a={LONG_VALUE}"[: container.MAX_PRINTABLE + 3] + "...",
        )


class TestHeaders(unittest.TestCase):
    def test_icontains(self):
        headers = Headers([("Content-Type", "text/html")])

        self.assertTrue(headers.icontains("content-type"))
        self.assertFalse(headers.icontains("server"))

    def test_invalid_name_and_value(self):
        headers = Headers()

        self.assertRaises(TypeError, headers.__setitem__, 1, "a")
        self.assertRaises(TypeError, headers.__setitem__, "a", 1)


class TestPlainContainer(unittest.TestCase):
    def test_deepcopy(self):
        container = PlainContainer("abc", "text/plain")

        clone = copy.deepcopy(container)

        self.assertEqual(str(clone), "abc")
        self.assertEqual(clone.get_headers(), [("content-type", "text/plain")])

    def test_short_printable_repr(self):
        container = PlainContainer(LONG_VALUE)

        self.assertEqual(
            container.get_short_printable_repr(), LONG_VALUE[: container.MAX_PRINTABLE]
        )


class TestJSONContainer(unittest.TestCase):
    def test_invalid_input(self):
        self.assertRaises(TypeError, JSONContainer, b"{}")
        self.assertRaises(ValueError, JSONContainer, "{not json")

    def test_repr(self):
        self.assertEqual(repr(JSONContainer("{}")), "<JSONContainer (token: None)>")

    def test_short_printable_repr_without_token(self):
        self.assertEqual(
            JSONContainer('{"a": 1}').get_short_printable_repr(), '{"a": 1}'
        )


class TestMultipartContainer(unittest.TestCase):
    def test_header_injection_in_content_type(self):
        headers = Headers([("Content-Type", "multipart/form-data; boundary=a\rb")])

        self.assertRaises(
            ValueError, MultipartContainer.from_postdata, headers, "--a--\r\n"
        )

    def test_parts_without_name_are_ignored(self):
        headers = Headers([("Content-Type", "multipart/form-data; boundary=b")])
        post_data = (
            "--b\r\n"
            "Content-Disposition: form-data\r\n\r\n"
            "anonymous\r\n"
            "--b\r\n"
            'Content-Disposition: form-data; name="a"\r\n\r\n'
            "1\r\n"
            "--b--\r\n"
        )

        container = MultipartContainer.from_postdata(headers, post_data)

        self.assertEqual(list(container.keys()), ["a"])

    def test_get_headers(self):
        container = MultipartContainer()

        self.assertEqual(
            container.get_headers(),
            [("Content-Type", f"multipart/form-data; boundary={container.boundary}")],
        )


class TestQueryString(unittest.TestCase):
    def test_invalid_values(self):
        query_string = QueryString()

        self.assertRaises(TypeError, query_string.__setitem__, "a", "1")
        self.assertRaises(TypeError, query_string.__setitem__, "a", [1])


class TestURLEncodedForm(unittest.TestCase):
    def test_from_postdata_requires_text(self):
        headers = Headers([("Content-Type", URLEncodedForm.ENCODING)])

        self.assertFalse(URLEncodedForm.can_parse(b"a=1"))
        self.assertRaises(ValueError, URLEncodedForm.from_postdata, headers, b"a=1")

    def test_form_proxies_its_parameters(self):
        form_params = FormParameters()
        form_params.add_field_by_attrs({"name": "a", "type": "checkbox", "value": ""})
        form_params.add_field_by_attrs({"name": "b", "type": "text", "value": ""})
        form = URLEncodedForm(form_params)

        form.smart_fill()
        form.update(c=["3"])

        self.assertEqual(form["a"], [""])
        self.assertNotEqual(form["b"], [""])
        self.assertEqual(list(form), ["a", "b", "c"])
        self.assertEqual(list(reversed(form)), ["c", "b", "a"])
        self.assertIsNone(form.get_autocomplete())


class TestFactory(unittest.TestCase):
    def test_missing_headers_fall_back_to_plain(self):
        self.assertIsInstance(dc_from_hdrs_post(None, "raw"), PlainContainer)

    def test_unknown_content_type(self):
        self.assertIsNone(dc_from_content_type_and_raw_params("text/plain", {}))


class TestTokens(unittest.TestCase):
    def test_data_token_api(self):
        token = DataToken("a", "1", ("a", 0))
        token.set_value("2")

        self.assertEqual(token.get_payload(), "2")
        self.assertEqual(repr(token), "<DataToken for ('a', 0): \"2\">")
        self.assertFalse(token.__eq__(None))
        self.assertRaises(RuntimeError, token.__eq__, 1)

    def test_file_token_extension_from_filename(self):
        self.assertEqual(FileDataToken("f", "x", "a.png", ("f",))._extension, "png")
        self.assertEqual(FileDataToken("f", "x", "a.", ("f",))._extension, "gif")


class TestMultipartSplit(unittest.TestCase):
    def test_closed_files_are_sent_empty(self):
        form_params = FormParameters()
        form_params.add_field_by_attrs({"name": "f", "type": "file", "value": ""})
        container = MultipartContainer(form_params)
        upload = NamedStringIO("content", "a.txt")
        upload._stream.close()
        container["f"] = [upload]

        self.assertEqual(_split_vars_files(container), ([("f", "")], []))


class TestDateTimeJSONEncoder(unittest.TestCase):
    def test_dates(self):
        value = {"when": datetime.date(2020, 1, 2)}

        self.assertEqual(
            json.dumps(value, cls=DateTimeJSONEncoder), '{"when": "2020-01-02"}'
        )

    def test_unsupported_object(self):
        self.assertRaises(TypeError, json.dumps, object(), cls=DateTimeJSONEncoder)


class TestXmlRpcContainer(unittest.TestCase):
    def test_invalid_input(self):
        self.assertRaises(TypeError, XmlRpcContainer, b"<methodCall/>")
        self.assertRaises(ValueError, XmlRpcContainer, "<methodCall><params")

    def test_get_headers(self):
        container = XmlRpcContainer(
            "<methodCall><methodName>a</methodName></methodCall>"
        )

        self.assertEqual(container.get_headers(), [("Content-Type", "text/xml")])
