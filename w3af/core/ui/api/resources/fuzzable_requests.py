"""
fuzzable_requests.py

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

from flask import Response

from w3af.core.ui.api.application import app
from w3af.core.ui.api.resources.traffic import encode_message
from w3af.core.ui.api.utils.auth import requires_auth
from w3af.core.ui.api.utils.error import abort
from w3af.core.ui.api.utils.json_stream import stream_json_items
from w3af.core.ui.api.utils.scans import get_scan_core, get_scan_info_from_id


@app.route("/scans/<int:scan_id>/fuzzable-requests/", methods=["GET"])
@requires_auth
def get_fuzzable_request_list(scan_id):
    """
    A list with all the known fuzzable requests by this scanner

    :param scan_id: The scan ID
    :return: Fuzzable requests (serialized as base64 encoded string) in a list
    """
    scan_info = get_scan_info_from_id(scan_id)
    if scan_info is None:
        abort(404, "Scan not found")

    knowledge_base = get_scan_core(scan_info).knowledge_base
    requests = (
        encode_message(fuzzable_request.dump())
        for fuzzable_request in knowledge_base.get_all_known_fuzzable_requests()
    )
    return Response(stream_json_items(requests), mimetype="application/json")
