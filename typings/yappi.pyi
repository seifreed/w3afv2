from collections.abc import Callable
from typing import Any

class YFuncStats:
    def save(self, path: str, type: str = "ystat") -> None: ...

def start(
    builtins: bool = False, profile_threads: bool = True, profile_greenlets: bool = True
) -> None: ...
def get_func_stats(
    tag: int | None = None,
    ctx_id: int | None = None,
    filter: dict[str, Any] | None = None,
    filter_callback: Callable[[Any], bool] | None = None,
) -> YFuncStats: ...
