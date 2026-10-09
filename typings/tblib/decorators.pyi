from collections.abc import Callable
from types import TracebackType

class Error:
    exc_type: type[BaseException]
    exc_value: BaseException
    def __init__(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType | None,
    ) -> None: ...
    @property
    def traceback(self) -> TracebackType | None: ...
    def reraise(self) -> None: ...

def return_error[**P, R](
    func: Callable[P, R], exc_type: type[BaseException] = ...
) -> Callable[P, R | Error]: ...
