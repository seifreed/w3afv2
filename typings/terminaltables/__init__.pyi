from collections.abc import Sequence

class AsciiTable:
    def __init__(
        self, table_data: Sequence[Sequence[object]], title: str | None = None
    ) -> None: ...
    @property
    def table(self) -> str: ...
