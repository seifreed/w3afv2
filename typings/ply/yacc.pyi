from types import ModuleType
from typing import Any

class LRParser:
    def parse(
        self,
        input: str | None = None,
        lexer: Any = None,
        debug: bool = False,
        tracking: bool = False,
        tokenfunc: Any = None,
    ) -> Any: ...

def yacc(
    method: str = "LALR",
    debug: bool | int = ...,
    module: ModuleType | None = None,
    tabmodule: str = ...,
    start: str | None = None,
    check_recursion: bool = True,
    optimize: bool = False,
    write_tables: bool | int = True,
    debugfile: str = ...,
    outputdir: str | None = None,
    debuglog: Any = None,
    errorlog: Any = None,
    picklefile: str | None = None,
) -> LRParser: ...
