class diff_match_patch:
    Diff_Timeout: float
    def __init__(self) -> None: ...
    def diff_main(
        self,
        text1: str,
        text2: str,
        checklines: bool = True,
        deadline: float | None = None,
    ) -> list[tuple[int, str]]: ...
    def diff_cleanupSemantic(self, diffs: list[tuple[int, str]]) -> None: ...
