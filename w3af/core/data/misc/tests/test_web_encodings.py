"""Tests for the URL, HTML and JSON encoders used to clean response bodies."""

import unittest

from w3af.core.data.misc.web_encodings import (
    HTML_ENCODING_FUNCTIONS,
    JSON_ENCODING_FUNCTIONS,
    URL_ENCODING_FUNCTIONS,
    backslash_escape,
    generate_html_encoding_functions,
    generate_url_encoding_functions,
    html_encode,
    unicode_escape,
    url_encode,
)


def encoding_functions():
    if not HTML_ENCODING_FUNCTIONS:
        generate_html_encoding_functions()
        generate_url_encoding_functions()

    return URL_ENCODING_FUNCTIONS, HTML_ENCODING_FUNCTIONS


class TestURLEncoding(unittest.TestCase):
    def test_url_encode_only_replaces_selected_chars(self):
        encoded = url_encode(
            "a/b c", by_code_replacer=lambda c: "%20", replace_by_code={" "}
        )

        self.assertEqual(encoded, "a/b%20c")

    def test_generated_functions(self):
        url_functions, _ = encoding_functions()

        self.assertEqual(len(url_functions), 18)
        self.assertEqual(
            {encode('a/b c<"') for encode in url_functions},
            {
                'a/b c<"',
                'a%2fb c<"',
                "a%2fb%20c%3c%22",
                "a%2fb+c%3c%22",
                "%61%2f%62%20%63%3c%22",
                "%61%2f%62+%63%3c%22",
            },
        )


class TestHTMLEncoding(unittest.TestCase):
    def test_names_take_precedence_over_codes(self):
        encoded = html_encode(
            "<a>",
            by_code_replacer=lambda c: "&#60;",
            by_name_replacer=lambda c: "&lt;",
            replace_by_code={"<", ">"},
            replace_by_name={"<"},
        )

        self.assertEqual(encoded, "&lt;a&#60;")

    def test_generated_functions(self):
        _, html_functions = encoding_functions()
        encoded = {encode('<a&"') for encode in html_functions}

        self.assertEqual(len(html_functions), 240)
        self.assertIn('<a&"', encoded)
        self.assertIn("&lt;a&amp;&quot;", encoded)
        self.assertIn("&#x3c;&#x61;&#x26;&#x22;", encoded)
        self.assertIn("&#60;a&#38;&#34;", encoded)
        self.assertIn("&#060;&#097;&#038;&#034;", encoded)


class TestJSONEncoding(unittest.TestCase):
    def test_unicode_escape(self):
        self.assertEqual(unicode_escape("\"'"), "\\u0022\\u0027")

    def test_backslash_escape(self):
        self.assertEqual(backslash_escape("\"'"), "\\\"\\'")

    def test_json_functions(self):
        self.assertEqual(JSON_ENCODING_FUNCTIONS, (unicode_escape, backslash_escape))
