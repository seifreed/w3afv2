from collections.abc import Callable

from astroid.nodes.node_ng import NodeNG

class AstroidManager:
    def register_transform[N: NodeNG](
        self,
        node_class: type[N],
        transform: Callable[[N], N | None],
        predicate: Callable[[N], bool] | None = None,
    ) -> None: ...
