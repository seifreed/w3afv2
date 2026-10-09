"""
main.py

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""

import argparse
import logging
import webbrowser
from argparse import ArgumentTypeError
from collections.abc import Sequence

from w3af.core.ui.api import app
from w3af.core.ui.api.utils import cli
from w3af.core.ui.api.utils.mp_flask import create_server, server_url
from w3af.core.ui.web.views import UI_PREFIX, register

DESCRIPTION = "Web user interface for w3af"

register(app)


def build_parser() -> argparse.ArgumentParser:
    parser = cli.build_parser(DESCRIPTION)
    parser.add_argument(
        "--no-browser",
        dest="no_browser",
        action="store_true",
        help="Do not open the web user interface in the default browser",
    )
    return parser


def ui_url(host: str, port: int, use_ssl: bool) -> str:
    """
    :return: The URL where the web user interface is served
    """
    return f"{server_url(host, port, use_ssl)}{UI_PREFIX}/"


def main(argv: Sequence[str] | None = None) -> int:
    """
    Entry point for the web user interface: serve the REST API and the web UI.
    Werkzeug exits with status 1 when the address can not be bound.

    :return: Zero if everything went well
    """
    try:
        args = cli.process_cmd_args_config(app, argv, build_parser())
    except ArgumentTypeError as argument_error:
        print(argument_error)
        return 1

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    server = create_server(app)
    url = ui_url(app.config["HOST"], server.server_port, server.ssl_context is not None)
    print(f"w3af web user interface available at {url}")

    if not args.no_browser:
        webbrowser.open(url)

    # Werkzeug stops serving on CTRL+C and closes the socket
    server.serve_forever()
    print("The w3af web user interface was stopped.")
    return 0
