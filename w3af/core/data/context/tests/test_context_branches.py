"""Break-out and execution decisions for individual HTML/CSS/JS contexts."""

import unittest

from w3af.core.data.context.context import get_context
from w3af.core.data.context.context.css import (
    GenericStyleContext,
    StyleDoubleQuoteString,
    get_css_context_iter,
)
from w3af.core.data.context.context.html import (
    CSSText,
    HtmlAttrDoubleQuote,
    HtmlDeclaration,
    HtmlProcessingInstruction,
    ScriptText,
)
from w3af.core.data.context.context.javascript import (
    ScriptExecutableContext,
    get_js_context_iter,
)

PAYLOAD = "PAYLOAD"


def context_types(contexts):
    return [type(context) for context in contexts]


class TestParsers(unittest.TestCase):
    def test_payload_not_in_data(self):
        self.assertEqual(list(get_css_context_iter("a{}", PAYLOAD)), [])
        self.assertEqual(list(get_js_context_iter("a();", PAYLOAD)), [])

    def test_css_escaped_quote_inside_string(self):
        contexts = get_css_context_iter('a{b:"x\\"PAYLOAD"}', PAYLOAD)

        self.assertEqual(context_types(contexts), [StyleDoubleQuoteString])

    def test_css_payload_before_string(self):
        contexts = get_css_context_iter('PAYLOAD "str"', PAYLOAD)

        self.assertEqual(context_types(contexts), [GenericStyleContext])

    def test_css_payload_before_comment(self):
        contexts = get_css_context_iter("PAYLOAD /* c */", PAYLOAD)

        self.assertEqual(context_types(contexts), [GenericStyleContext])

    def test_js_payload_before_comment(self):
        contexts = get_js_context_iter("a();PAYLOAD /* c */", PAYLOAD)

        self.assertEqual(context_types(contexts), [ScriptExecutableContext])

    def test_html_declaration(self):
        contexts = get_context("<!DOCTYPE PAYLOAD>", PAYLOAD)

        self.assertEqual(context_types(contexts), [HtmlDeclaration])

    def test_html_processing_instruction(self):
        contexts = get_context("<?xml PAYLOAD?>", PAYLOAD)

        self.assertEqual(context_types(contexts), [HtmlProcessingInstruction])


class TestScriptText(unittest.TestCase):
    def test_can_break_closing_the_tag(self):
        self.assertTrue(ScriptText("</s", "a(); </s").can_break())

    def test_executable_code(self):
        self.assertTrue(ScriptText(PAYLOAD, "foo();PAYLOAD;").is_executable())

    def test_payload_inside_string_is_not_executable(self):
        self.assertFalse(ScriptText(PAYLOAD, 'a="PAYLOAD";').is_executable())


class TestCSSText(unittest.TestCase):
    def test_can_break_closing_the_tag(self):
        self.assertTrue(CSSText("<x", "a{} <x").can_break())

    def test_payload_inside_string_can_not_break(self):
        self.assertFalse(CSSText(PAYLOAD, 'a{b:"PAYLOAD"}').can_break())


class TestHtmlAttribute(unittest.TestCase):
    def test_can_break_with_the_delimiter(self):
        self.assertTrue(HtmlAttrDoubleQuote('a"b', "title", 'a"b').can_break())

    def test_style_payload_inside_string(self):
        attribute = HtmlAttrDoubleQuote(PAYLOAD, "style", 'color:"PAYLOAD"')

        self.assertFalse(attribute.can_break())
        self.assertFalse(attribute.is_executable())

    def test_href_without_javascript_protocol(self):
        attribute = HtmlAttrDoubleQuote(PAYLOAD, "href", PAYLOAD)

        self.assertFalse(attribute.can_break())
        self.assertFalse(attribute.is_executable())

    def test_href_javascript_protocol_payload_in_string(self):
        attribute = HtmlAttrDoubleQuote(PAYLOAD, "href", 'javascript:a("PAYLOAD")')

        self.assertFalse(attribute.can_break())
        self.assertFalse(attribute.is_executable())

    def test_event_payload_in_string_is_not_executable(self):
        attribute = HtmlAttrDoubleQuote(PAYLOAD, "onclick", 'a("PAYLOAD")')

        self.assertFalse(attribute.is_executable())
