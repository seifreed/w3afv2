"""
views.py

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

from flask import Blueprint, Flask, Response

from w3af.core.ui.api.utils.auth import requires_auth

UI_PREFIX = "/ui"

CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self';"
    " connect-src 'self'; base-uri 'none'; form-action 'none';"
    " frame-ancestors 'none'"
)

blueprint = Blueprint(
    "web_ui",
    __name__,
    static_folder="static",
    static_url_path="/static",
    url_prefix=UI_PREFIX,
)


@blueprint.before_request
@requires_auth
def authenticate() -> None:
    """
    Every page and asset of the web UI requires the REST API credentials, which
    the browser then sends with each API call.
    """


@blueprint.after_request
def add_content_security_policy(response: Response) -> Response:
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@blueprint.route("/", methods=["GET"])
def index() -> Response:
    return blueprint.send_static_file("index.html")


def register(app: Flask) -> None:
    """
    Serve the web UI from the REST API application
    """
    if blueprint.name not in app.blueprints:
        app.register_blueprint(blueprint)
