"""Streaming helpers for JSON API responses."""

import json
from collections.abc import Iterable, Iterator


def stream_json_items(items: Iterable[object]) -> Iterator[str]:
    """Yield a JSON object containing an items array without materializing it."""
    yield '{"items":['

    for index, item in enumerate(items):
        if index:
            yield ","
        yield json.dumps(item)

    yield "]}"
