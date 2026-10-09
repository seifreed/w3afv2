from astroid.nodes.node_ng import NodeNG

class Module(NodeNG): ...

class ClassDef(NodeNG):
    name: str
    locals: dict[str, list[NodeNG]]
    def __init__(
        self,
        name: str,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None: ...
