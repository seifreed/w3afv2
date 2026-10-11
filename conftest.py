"""Shared pytest cleanup for resources owned by cyclic test objects."""

import gc
import threading
from collections.abc import Iterator

import pytest


def _has_output_manager_threads() -> bool:
    return any(
        thread.name.startswith("OutputManager") for thread in threading.enumerate()
    )


@pytest.fixture(autouse=True)
def release_cyclic_test_resources() -> Iterator[None]:
    yield
    if _has_output_manager_threads():
        gc.collect()
