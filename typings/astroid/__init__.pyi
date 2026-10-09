from collections.abc import Callable

from astroid.manager import AstroidManager
from astroid.nodes import scoped_nodes as scoped_nodes
from astroid.nodes.scoped_nodes import Module

MANAGER: AstroidManager

def register_module_extender(
    manager: AstroidManager,
    module_name: str,
    get_extension_mod: Callable[[], Module],
) -> None: ...
