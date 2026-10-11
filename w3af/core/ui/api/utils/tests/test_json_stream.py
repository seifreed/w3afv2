"""Tests for streaming JSON API helpers."""

import json

from w3af.core.ui.api.utils.json_stream import stream_json_items


def test_stream_json_items_serializes_multiple_items_incrementally():
    chunks = stream_json_items(item for item in ["first", "second"])

    assert json.loads("".join(chunks)) == {"items": ["first", "second"]}


def test_stream_json_items_serializes_empty_iterables():
    chunks = stream_json_items(iter(()))

    assert json.loads("".join(chunks)) == {"items": []}
