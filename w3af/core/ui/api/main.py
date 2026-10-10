"""
main.py

Copyright 2015 Andres Riancho

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

import logging
from argparse import ArgumentTypeError
from collections.abc import Sequence

from w3af.core.ui.api.application import app
from w3af.core.ui.api.utils import cli
from w3af.core.ui.api.utils.mp_flask import create_server, server_url


def main(argv: Sequence[str] | None = None) -> int:
    """
    Entry point for the REST API. Werkzeug exits with status 1 when the
    address can not be bound.

    :return: Zero if everything went well
    """
    try:
        args = cli.process_cmd_args_config(app, argv)
    except ArgumentTypeError as argument_error:
        print(argument_error)
        return 1

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    server = create_server(app)
    use_ssl = server.ssl_context is not None
    url = server_url(app.config["HOST"], server.server_port, use_ssl)
    print(f"w3af REST API available at {url}/")

    # Werkzeug stops serving on CTRL+C and closes the socket
    server.serve_forever()
    print("The w3af REST API was stopped.")
    return 0
