from collections.abc import Iterator
from typing import IO, Self

class DSStoreEntry:
    filename: str

class DSStore:
    @classmethod
    def open(
        cls,
        file_or_name: str | IO[bytes],
        mode: str = "r+",
        initial_entries: list[DSStoreEntry] | None = None,
    ) -> Self: ...
    def __iter__(self) -> Iterator[DSStoreEntry]: ...
