from flask import Flask

app = Flask("w3af")

from . import middlewares, resources

__all__ = ["app", "middlewares", "resources"]
