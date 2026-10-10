"""
A small evaluator of SQL WHERE conditions, enough to run the statements that
the blind SQL injection detection sends: comparisons between columns, numbers
and quoted strings combined with AND / OR.

It lets the test applications behave like a database that is vulnerable to SQL
injection: the user input is placed inside the condition and the condition is
parsed and evaluated, so the injected statements change the result the way they
do in a real database, and malformed statements fail with a syntax error.
"""

import re

TOKEN_PATTERN = re.compile(r"\s*(?:(\d+)|'([^']*)'|([A-Za-z_]\w*)|(=))")
KEYWORDS = ("AND", "OR")


class SqlSyntaxError(Exception):
    pass


def tokenize(text: str) -> list[tuple[str, str]]:
    tokens = []
    position = 0

    while text[position:].strip():
        match = TOKEN_PATTERN.match(text, position)
        if match is None:
            raise SqlSyntaxError(f"unexpected input near {text[position:]!r}")

        number, string, word, equals = match.groups()
        if number is not None:
            tokens.append(("number", number))
        elif string is not None:
            tokens.append(("string", string))
        elif word is not None:
            kind = "keyword" if word.upper() in KEYWORDS else "column"
            tokens.append((kind, word))
        else:
            tokens.append(("equals", equals))
        position = match.end()

    return tokens


class WhereClause:
    """
    Grammar:
        condition  := conjunction (OR conjunction)*
        conjunction := comparison (AND comparison)*
        comparison := operand ('=' operand)?
        operand    := number | 'string' | column
    """

    def __init__(self, text: str, row: dict[str, object]):
        self._tokens = tokenize(text)
        self._row = row
        self._position = 0

    def matches(self) -> bool:
        result = self._condition()
        if self._position != len(self._tokens):
            raise SqlSyntaxError("unexpected token after the condition")
        return bool(result)

    def _peek_keyword(self, keyword: str) -> bool:
        if self._position == len(self._tokens):
            return False

        kind, value = self._tokens[self._position]
        return kind == "keyword" and value.upper() == keyword

    def _condition(self):
        result = self._conjunction()
        while self._peek_keyword("OR"):
            self._position += 1
            result = self._conjunction() or result
        return result

    def _conjunction(self):
        result = self._comparison()
        while self._peek_keyword("AND"):
            self._position += 1
            result = self._comparison() and result
        return result

    def _comparison(self):
        left = self._operand()
        if self._position < len(self._tokens) and (
            self._tokens[self._position][0] == "equals"
        ):
            self._position += 1
            return left == self._operand()
        return left

    def _operand(self):
        if self._position == len(self._tokens):
            raise SqlSyntaxError("unexpected end of the condition")

        kind, value = self._tokens[self._position]
        self._position += 1

        if kind == "number":
            return int(value)
        if kind == "string":
            return value
        if kind == "column" and value in self._row:
            return self._row[value]
        raise SqlSyntaxError(f"unexpected {value!r}")
