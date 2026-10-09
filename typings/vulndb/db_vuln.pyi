from collections.abc import Iterator
from typing import Any, Self

class Reference:
    url: str
    title: str
    def __init__(self, url: str, title: str) -> None: ...

class DBVuln:
    DEFAULT_LANG: str
    id: int
    title: str
    description: str
    severity: str
    wasc: list[str]
    tags: list[str]
    cwe: list[str]
    owasp_top_10: dict[str, list[int]]
    fix_guidance: str
    fix_effort: int
    references: list[Reference]
    db_file: str
    def __init__(
        self,
        _id: int | None = None,
        title: str | None = None,
        description: str | None = None,
        severity: str | None = None,
        wasc: list[str] | None = None,
        tags: list[str] | None = None,
        cwe: list[str] | None = None,
        owasp_top_10: dict[str, list[int]] | None = None,
        fix_guidance: str | None = None,
        fix_effort: int | None = None,
        references: list[Reference] | None = None,
        db_file: str | None = None,
    ) -> None: ...
    @staticmethod
    def get_all_languages() -> list[str]: ...
    @classmethod
    def from_id(cls, _id: Any, language: str = ...) -> Self: ...
    def get_owasp_top_10_references(self) -> Iterator[tuple[str, int, str]]: ...
    @staticmethod
    def get_all_db_ids(language: str = ...) -> list[str]: ...
    @staticmethod
    def get_wasc_url(wasc_id: str) -> str | None: ...
    @staticmethod
    def get_cwe_url(cwe_id: str) -> str: ...
    @staticmethod
    def is_valid_id(_id: Any, language: str = ...) -> bool: ...
