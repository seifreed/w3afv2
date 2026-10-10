import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def environment_variable(name: str, value: str | None) -> Iterator[None]:
    """Set (or unset when value is None) a real env var and restore it."""
    previous = os.environ.get(name)
    _assign(name, value)
    try:
        yield
    finally:
        _assign(name, previous)


def _assign(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


@contextmanager
def file_content(path: str, content: str | None) -> Iterator[None]:
    """Write (or remove when content is None) a real file and restore it."""
    target = Path(path)
    previous = target.read_text() if target.exists() else None
    _store(target, content)
    try:
        yield
    finally:
        _store(target, previous)


def _store(target: Path, content: str | None) -> None:
    if content is None:
        target.unlink(missing_ok=True)
    else:
        target.write_text(content)
