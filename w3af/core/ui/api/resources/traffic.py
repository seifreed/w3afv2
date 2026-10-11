"""
traffic.py

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

from base64 import b64encode

from flask import jsonify

from w3af.core.data.db.exceptions import DBException
from w3af.core.data.db.history import HistoryItem
from w3af.core.ui.api.application import app
from w3af.core.ui.api.utils.auth import requires_auth
from w3af.core.ui.api.utils.error import abort
from w3af.core.ui.api.utils.scans import get_scan_core, get_scan_info_from_id


@app.route("/scans/<int:scan_id>/traffic/<int:traffic_id>", methods=["GET"])
@requires_auth
def get_traffic_details(scan_id, traffic_id):
    """
    The HTTP request and response associated with a vulnerability, usually the
    user will first get /scans/1/kb/3 and from there (if needed) browse to
    this resource where the HTTP traffic is available

    :param scan_id: The scan ID
    :param traffic_id: The ID of the request/response
    :return: HTTP request and response in base64 format
    """
    scan_info = get_scan_info_from_id(scan_id)
    if scan_info is None:
        abort(404, "Scan not found")

    history_db = HistoryItem(db=get_scan_core(scan_info).database)

    try:
        details = history_db.read(traffic_id)
    except DBException:
        abort(404, f"Failed to retrieve request with id {traffic_id} from DB.")

    data = {
        "request": encode_message(details.request.dump()),
        "response": encode_message(details.response.dump()),
    }

    return jsonify(data)


def encode_message(message: str | bytes) -> str:
    """
    :return: The HTTP message encoded as base64 text, ready to be sent as JSON
    """
    if isinstance(message, str):
        message = message.encode("utf-8", errors="surrogateescape")
    return b64encode(message).decode("ascii")
