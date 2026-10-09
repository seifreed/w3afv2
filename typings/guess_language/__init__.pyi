from collections.abc import Iterable

class UNKNOWN: ...

def guess_language(
    text: str, hints: Iterable[str] | None = None
) -> str | type[UNKNOWN]: ...
