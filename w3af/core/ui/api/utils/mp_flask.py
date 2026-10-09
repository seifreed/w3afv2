from multiprocessing.dummy import Process
from socketserver import ThreadingMixIn

from flask import Flask
from werkzeug.serving import BaseWSGIServer

from w3af.core.ui.api.utils.digital_certificate import SSLCertificate


class ThreadedWSGIServer(ThreadingMixIn, BaseWSGIServer):
    """
    A WSGI server that handles each request in a thread started with
    multiprocessing.dummy, which avoids the "'Thread' object has no attribute
    '_children'" error raised when the scan code starts its own processes.

    https://circleci.com/gh/andresriancho/w3af-api-docker/50
    """

    multithread = True

    def process_request(self, request, client_address):
        thread = Process(
            target=self.process_request_thread, args=(request, client_address)
        )
        thread.daemon = self.daemon_threads
        thread.start()


def make_server(host, port, app, ssl_context=None):
    """
    Werkzeug exits with status 1 when the address can not be bound.
    """
    return ThreadedWSGIServer(host, port, app, ssl_context=ssl_context)


def ssl_context(flask_app: Flask) -> tuple[str, str] | None:
    if flask_app.config["DISABLE_SSL"]:
        return None
    return SSLCertificate().get_cert_key(flask_app.config["HOST"])


def create_server(flask_app: Flask) -> ThreadedWSGIServer:
    return make_server(
        flask_app.config["HOST"],
        flask_app.config["PORT"],
        flask_app,
        ssl_context=ssl_context(flask_app),
    )


def server_url(host: str, port: int, use_ssl: bool) -> str:
    """
    :return: The base URL where a server listening on host:port is reachable
    """
    scheme = "https" if use_ssl else "http"
    display_host = f"[{host}]" if ":" in host else host
    return f"{scheme}://{display_host}:{port}"
