from .utils.mp_flask import ThreadedFlask

app = ThreadedFlask("w3af")

from . import middlewares, resources

__all__ = ["app", "middlewares", "resources"]
