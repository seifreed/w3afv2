"""Tests for streaming JSON API helpers."""

import json

from w3af.core.ui.api.utils.json_stream import stream_json_items


def test_stream_json_items_serializes_multiple_items_incrementally():
    chunks = stream_json_items(item for item in ["first", "second"])

    actual = json.loads("".join(chunks))
    if actual != {"items": ["first", "second"]}:
        raise AssertionError(actual)


def test_stream_json_items_serializes_empty_iterables():
    chunks = stream_json_items(iter(()))

    actual = json.loads("".join(chunks))
    if actual != {"items": []}:
        raise AssertionError(actual)
