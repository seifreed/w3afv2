from astroid.manager import AstroidManager
from astroid.nodes.scoped_nodes import Module

class AstroidBuilder:
    def __init__(
        self, manager: AstroidManager, apply_transforms: bool = True
    ) -> None: ...
    def string_build(
        self, data: str, modname: str = "", path: str | None = None
    ) -> Module: ...
