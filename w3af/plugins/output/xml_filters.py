"""Pure XML escaping filters used by the XML output plugin."""

from unicodedata import category

from w3af.core.data.misc.encoding import smart_unicode

__all__ = [
    "ATTR_VALUE_ESCAPES",
    "ATTR_VALUE_ESCAPES_IGNORE",
    "TEXT_VALUE_ESCAPES",
    "TEXT_VALUE_ESCAPES_IGNORE",
    "is_unicode_escape",
    "jinja2_attr_value_escape_filter",
    "jinja2_text_value_escape_filter",
]


def is_unicode_escape(i):
    return category(chr(i)).startswith("C")


ATTR_VALUE_ESCAPES = {
    '"': "&quot;",
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    # Note that here we replace tabs with 4-spaces, like in python ;-)
    # but it makes sense for easy parsing and showing to users
    "\t": "    ",
}

ATTR_VALUE_ESCAPES_IGNORE = {"\n", "\r"}


class _PreEscaped(str):
    """Mark a filter result so Jinja2 does not escape it a second time."""

    def __html__(self):
        return self


def jinja2_attr_value_escape_filter(value):
    """Escape a value used in an XML attribute."""
    if not isinstance(value, str):
        return value

    value = smart_unicode(value)
    result = []

    for letter in value:
        if letter in ATTR_VALUE_ESCAPES_IGNORE:
            result.append(letter)
            continue

        escape = _get_escape(
            letter,
            ATTR_VALUE_ESCAPES,
            "&lt;character code=&quot;%04x&quot;/&gt;",
        )
        result.append(letter if escape is None else escape)

    return _PreEscaped("".join(result))


TEXT_VALUE_ESCAPES = {
    '"': "&quot;",
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    # Note that here we replace tabs with 4-spaces, like in python ;-)
    # but it makes sense for easy parsing and showing to users
    "\t": "    ",
}

TEXT_VALUE_ESCAPES_IGNORE = {"\n", "\r"}


def _get_escape(letter, escapes, unicode_escape_template):
    codepoint = ord(letter)
    if is_unicode_escape(codepoint):
        return unicode_escape_template % codepoint
    return escapes.get(letter)


def jinja2_text_value_escape_filter(value):
    """Escape a value used as XML text."""
    if not isinstance(value, str):
        return value

    value = smart_unicode(value)
    result = []

    for letter in value:
        if letter in TEXT_VALUE_ESCAPES_IGNORE:
            result.append(letter)
            continue

        escape = _get_escape(letter, TEXT_VALUE_ESCAPES, '<character code="%04x"/>')
        result.append(letter if escape is None else escape)

    return _PreEscaped("".join(result))
