"""Less common paths of the fuzzer, its utilities and the mutant classes."""

import unittest

from w3af.core.data.dc.generic.nr_kv_container import NonRepeatKeyValueContainer
from w3af.core.data.dc.headers import Headers
from w3af.core.data.dc.multipart_container import MultipartContainer
from w3af.core.data.dc.utils.token import DataToken
from w3af.core.data.fuzzer.fuzzer import create_mutants
from w3af.core.data.fuzzer.mutants.empty_mutant import EmptyMutant
from w3af.core.data.fuzzer.mutants.filecontent_mutant import (
    FileContentMutant,
    OnlyTokenFilesMultipartContainer,
)
from w3af.core.data.fuzzer.mutants.filename_mutant import FileNameMutant
from w3af.core.data.fuzzer.mutants.json_mutant import JSONMutant
from w3af.core.data.fuzzer.mutants.querystring_mutant import QSMutant
from w3af.core.data.fuzzer.mutants.urlparts_mutant import URLPartsMutant
from w3af.core.data.fuzzer.utils import create_format_string, rand_number
from w3af.core.data.kb.config import Config
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse

FUZZER_CONFIG = {
    "fuzz_form_files": True,
    "fuzzed_files_extension": "gif",
    "fuzz_url_filenames": True,
    "fuzz_url_parts": True,
}


class TestCreateMutantsWithOriginalResponse(unittest.TestCase):
    def setUp(self):
        backup = Config(cf_singleton)
        self.addCleanup(cf_singleton.update, backup)
        self.addCleanup(cf_singleton.clear)

        cf_singleton.save("fuzzable_headers", [])
        cf_singleton.save("fuzz_cookies", False)
        cf_singleton.save("fuzz_url_filenames", False)
        cf_singleton.save("fuzzed_files_extension", "gif")
        cf_singleton.save("fuzz_form_files", False)
        cf_singleton.save("fuzz_url_parts", False)

    def test_etag_and_body_are_linked(self):
        url = URL("http://w3af.org/?id=1")
        headers = Headers([("ETag", "abc")])
        response = HTTPResponse(200, "original body", headers, url, url)

        mutants = create_mutants(FuzzableRequest(url), ["x"], orig_resp=response)

        self.assertEqual(len(mutants), 1)
        self.assertEqual(mutants[0].get_original_response_body(), "original body")
        self.assertEqual(mutants[0].get_headers()["If-None-Match"], "abc")

    def test_response_without_etag(self):
        url = URL("http://w3af.org/?id=1")
        response = HTTPResponse(200, "body", Headers(), url, url)

        mutants = create_mutants(FuzzableRequest(url), ["x"], orig_resp=response)

        self.assertNotIn("If-None-Match", mutants[0].get_headers())


class TestFuzzerUtils(unittest.TestCase):
    def test_rand_number_excludes_digits(self):
        number = rand_number(50, exclude_numbers=(1, 2, 3, 4, 5, 6, 7, 8))

        self.assertEqual(set(number) - {"0", "9"}, set())

    def test_rand_number_without_digits(self):
        self.assertRaises(ValueError, rand_number, 5, exclude_numbers=range(10))

    def test_create_format_string(self):
        self.assertEqual(create_format_string(3), "%n%n%n")


class TestMutantShortcuts(unittest.TestCase):
    def build_mutant(self):
        mutant = QSMutant(FuzzableRequest(URL("http://w3af.org/?id=1")))
        mutant.set_token(("id", 0))
        mutant.set_token_value("payload")
        return mutant

    def test_token_shortcuts(self):
        mutant = self.build_mutant()

        self.assertEqual(mutant.get_token_payload(), "payload")
        self.assertEqual(mutant.get_token_original_value(), "1")
        self.assertEqual(mutant.get_eq_attrs(), ["_freq", "_original_response_body"])

    def test_set_token_value_without_token(self):
        mutant = EmptyMutant()

        self.assertRaises(AttributeError, mutant.set_token_value, "x")

    def test_append_requires_text_payloads(self):
        freq = FuzzableRequest(URL("http://w3af.org/?id=1"))

        self.assertRaises(
            RuntimeError, QSMutant.create_mutants, freq, [1], [], True, FUZZER_CONFIG
        )

    def test_empty_mutant_set_dc(self):
        mutant = EmptyMutant()
        container = NonRepeatKeyValueContainer([("a", "1")])

        mutant.set_dc(container)

        self.assertIs(mutant.get_dc(), container)


class TestMutantTypes(unittest.TestCase):
    def test_types(self):
        self.assertEqual(FileContentMutant.get_mutant_type(), "file content")
        self.assertEqual(JSONMutant.get_mutant_type(), "JSON data")


class TestOnlyTokenFilesMultipartContainer(unittest.TestCase):
    def build_container(self):
        headers = Headers([("Content-Type", "multipart/form-data; boundary=b")])
        post_data = (
            "--b\r\n"
            'Content-Disposition: form-data; name="image"; filename="logo.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
            "PNG\r\n"
            "--b--\r\n"
        )
        form = MultipartContainer.from_postdata(headers, post_data)
        return OnlyTokenFilesMultipartContainer(form.form_params)

    def test_file_token_uses_uploaded_file_extension(self):
        container = self.build_container()

        token = container.set_token(("image", 0))

        self.assertEqual(token.get_value().name[-4:], ".png")

    def test_existing_tokens_are_not_wrapped_twice(self):
        container = self.build_container()
        token = container.set_token(("image", 0))

        self.assertIs(container.set_token(("image", 0)), token)
        self.assertIsInstance(token, DataToken)


class TestFileNameMutant(unittest.TestCase):
    def test_only_selected_chunks_are_fuzzed(self):
        freq = FuzzableRequest(URL("http://w3af.org/foo.bar.html"))

        mutants = FileNameMutant.create_mutants(freq, ["x"], [2], False, FUZZER_CONFIG)

        self.assertEqual(
            [m.get_url().url_string for m in mutants], ["http://w3af.org/foo.x.html"]
        )


class TestURLPartsMutant(unittest.TestCase):
    def build_mutants(self):
        freq = FuzzableRequest(URL("http://w3af.org/static/foo/bar?x=1"))
        freq.set_force_fuzzing_url_parts(
            [("/static/", False), ("foo", True), ("/bar", False)]
        )
        return URLPartsMutant.create_mutants(freq, ["a/b"], [], False, FUZZER_CONFIG)

    def test_forced_parts_with_double_encoding(self):
        mutants = self.build_mutants()

        self.assertEqual(
            [m.get_uri().url_string for m in mutants],
            [
                "http://w3af.org/static/a%2Fb/bar?x=1",
                "http://w3af.org/static/a%252Fb/bar?x=1",
            ],
        )

    def test_url_can_not_be_changed(self):
        mutant = self.build_mutants()[0]

        self.assertRaises(ValueError, mutant.set_url, URL("http://w3af.org/"))


cf_singleton = Config()
