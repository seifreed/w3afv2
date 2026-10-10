import unittest

from w3af.core.controllers.sql_tools.tests.where_clause import (
    SqlSyntaxError,
    WhereClause,
    tokenize,
)

ROW = {"id": 12, "name": "pablo"}


def matches(condition):
    return WhereClause(condition, ROW).matches()


class TestTokenize(unittest.TestCase):
    def test_tokens_of_a_condition(self):
        self.assertEqual(
            tokenize("name = 'pablo' or id=12"),
            [
                ("column", "name"),
                ("equals", "="),
                ("string", "pablo"),
                ("keyword", "or"),
                ("column", "id"),
                ("equals", "="),
                ("number", "12"),
            ],
        )

    def test_unexpected_characters_are_syntax_errors(self):
        for text in ('id = 1"', "id = 'open", "id = 1; DROP", "id = (1)"):
            with self.subTest(text=text), self.assertRaises(SqlSyntaxError):
                tokenize(text)


class TestWhereClause(unittest.TestCase):
    def test_comparisons(self):
        self.assertTrue(matches("id = 12"))
        self.assertFalse(matches("id = 13"))
        self.assertTrue(matches("name = 'pablo'"))
        self.assertTrue(matches("12=12"))
        self.assertFalse(matches("'12'='13'"))

    def test_or_is_true_when_any_side_is_true(self):
        self.assertTrue(matches("id = 1 OR 12=12"))
        self.assertTrue(matches("id = 12 or 1=2"))
        self.assertFalse(matches("id = 1 OR 1=2"))

    def test_and_requires_both_sides_and_binds_tighter_than_or(self):
        self.assertTrue(matches("id = 12 AND name = 'pablo'"))
        self.assertFalse(matches("id = 12 AND 12=13"))
        self.assertTrue(matches("1=2 AND 1=2 OR 12=12"))

    def test_a_bare_operand_is_true_when_it_is_not_zero(self):
        self.assertTrue(matches("12"))
        self.assertFalse(matches("0"))

    def test_malformed_conditions_are_syntax_errors(self):
        for condition in (
            "id = ",
            "",
            "12 12",
            "unknown_column = 1",
            "id = 12 OR",
            "= 12",
        ):
            with self.subTest(condition=condition), self.assertRaises(SqlSyntaxError):
                matches(condition)
