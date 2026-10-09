from ply.lex import Lexer

class FilteredLexer:
    lexer: Lexer
    def __init__(self, lexer: Lexer) -> None: ...
    def clone(self) -> FilteredLexer: ...

lexer: FilteredLexer
