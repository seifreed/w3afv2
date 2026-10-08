from .utils.mp_flask import ThreadedFlask

app = ThreadedFlask("w3af")

from . import app, middlewares, resources
