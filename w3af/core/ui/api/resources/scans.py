"""
scans.py

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

from multiprocessing.dummy import Process

from flask import jsonify, request

from w3af.core.controllers.core_helpers.status import RUNNING, STOPPED
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.parsers.doc.url import URL
from w3af.core.exceptions import BaseFrameworkException
from w3af.core.ui.api.application import app
from w3af.core.ui.api.db.master import SCANS, ScanInfo
from w3af.core.ui.api.utils.auth import requires_auth
from w3af.core.ui.api.utils.error import abort
from w3af.core.ui.api.utils.log_handler import RESTAPIOutput
from w3af.core.ui.api.utils.scans import (
    create_temp_profile,
    get_new_scan_id,
    get_scan_info_from_id,
    remove_temp_profile,
    start_scan_helper,
)

STARTING = "Starting"


@app.route("/scans/", methods=["POST"])
@requires_auth
def start_scan():
    """
    Starts a new w3af scan

    Receive a JSON containing:
        - A list with the target URLs
        - The profile (eg. the content of fast_scan.pw3af)

    :return: A JSON containing:
        - The URL to the newly created scan (eg. /scans/1)
        - The newly created scan ID (eg. 1)
    """
    if not request.json or "scan_profile" not in request.json:
        abort(400, "Expected scan_profile in JSON object")

    if not request.json or "target_urls" not in request.json:
        abort(400, "Expected target_urls in JSON object")

    scan_profile = request.json["scan_profile"]
    target_urls = request.json["target_urls"]

    #
    # First make sure that there are no other scans running, remember that this
    # REST API is an MVP and we can only run one scan at the time (for now)
    #
    if any(scan_info is not None for scan_info in SCANS.values()):
        abort(
            400,
            "This version of the REST API does not support"
            " concurrent scans. Remember to DELETE finished scans"
            " before starting a new one.",
        )

    #
    # Before trying to start a new scan we verify that the scan profile is
    # valid and return an informative error if it's not
    #
    scan_profile_file_name, profile_path = create_temp_profile(scan_profile)
    w3af_core = w3afCore()

    try:
        w3af_core.profiles.use_profile(scan_profile_file_name, workdir=profile_path)
    except BaseFrameworkException as bfe:
        abort(400, str(bfe))
    finally:
        remove_temp_profile(scan_profile_file_name)

    #
    # Now that we know that the profile is valid I verify the scan target info
    #
    if target_urls is None or not len(target_urls):
        abort(400, "No target URLs specified")

    for target_url in target_urls:
        try:
            URL(target_url)
        except ValueError:
            abort(400, f'Invalid URL: "{target_url}"')

    target_options = w3af_core.target.get_options()
    target_option = target_options["target"]
    try:
        target_option.set_value([URL(u) for u in target_urls])
        w3af_core.target.set_options(target_options)
    except BaseFrameworkException as bfe:
        abort(400, str(bfe))

    scan_id = get_new_scan_id()
    scan_info = ScanInfo()
    scan_info.w3af_core = w3af_core
    scan_info.target_urls = target_urls
    scan_info.profile_path = scan_profile_file_name
    scan_info.output = RESTAPIOutput()
    SCANS[scan_id] = scan_info

    #
    # Finally, start the scan in a different thread
    #
    args = (scan_info,)
    t = Process(target=start_scan_helper, name="ScanThread", args=args)
    t.daemon = True

    t.start()

    return (
        jsonify({"message": "Success", "id": scan_id, "href": f"/scans/{scan_id}"}),
        201,
    )


@app.route("/scans/", methods=["GET"])
@requires_auth
def list_scans():
    """
    :return: A JSON containing a list of:
        - Scan resource URL (eg. /scans/1)
        - Scan target
        - Scan status
    """
    data = []

    for scan_id, scan_info in SCANS.items():

        if scan_info is None:
            continue

        target_urls = scan_info.target_urls
        core = scan_info.w3af_core
        if core is None:
            continue
        status = core.status.get_simplified_status()
        errors = scan_info.exception is not None

        data.append(
            {
                "id": scan_id,
                "href": f"/scans/{scan_id}",
                "target_urls": target_urls,
                "status": status,
                "errors": errors,
            }
        )

    return jsonify({"items": data})


@app.route("/scans/<int:scan_id>", methods=["DELETE"])
@requires_auth
def scan_delete(scan_id):
    """
    Clear all the scan information

    :param scan_id: The scan ID to stop
    :return: Empty result if success, 403 if the current state indicates that
             the scan can't be cleared.
    """
    scan_info = get_scan_info_from_id(scan_id)
    if scan_info is None:
        abort(404, "Scan not found")

    if scan_info.w3af_core is None:
        abort(400, "Scan state is invalid and can not be cleared")

    if not scan_info.w3af_core.can_cleanup():
        abort(403, "Scan is not ready to be cleared")

    scan_info.cleanup()
    SCANS.pop(scan_id, None)

    return jsonify({"message": "Success"})


@app.route("/scans/<int:scan_id>/status", methods=["GET"])
@requires_auth
def scan_status(scan_id):
    """
    :param scan_id: The scan ID
    :return: The scan status
    """
    scan_info = get_scan_info_from_id(scan_id)
    if scan_info is None:
        abort(404, "Scan not found")

    exc = scan_info.exception
    status = status_as_dict(scan_info)
    status["exception"] = exc if exc is None else str(exc)

    return jsonify(status)


def status_as_dict(scan_info):
    """
    :return: The scan status. Before the core starts the scan only the state is
             known: it is starting, or stopped if it failed to start.
    """
    core = scan_info.w3af_core
    if core is None:
        return {
            "status": STOPPED if scan_info.finished else STARTING,
            "is_paused": False,
            "is_running": False,
            "progress": 0,
        }

    core_status = core.status
    if core_status.has_started():
        return core_status.get_status_as_dict()

    return {
        "status": STOPPED if scan_info.finished else STARTING,
        "is_paused": False,
        "is_running": False,
        "progress": 0,
    }


@app.route("/scans/<int:scan_id>/pause", methods=["GET"])
@requires_auth
def scan_pause(scan_id):
    """
    Pause a scan

    :param scan_id: The scan ID to pause
    :return: Empty result if success, 403 if the current state indicates that
             the scan can't be paused.
    """
    scan_info = get_scan_info_from_id(scan_id)
    if scan_info is None:
        abort(404, "Scan not found")

    core = _get_scan_core(scan_info)
    if core.status.get_simplified_status() != RUNNING:
        abort(403, "Scan can not be paused")

    core.pause(True)

    return jsonify({"message": "Success"})


@app.route("/scans/<int:scan_id>/resume", methods=["GET"])
@requires_auth
def scan_resume(scan_id):
    """
    Resume a paused scan

    :param scan_id: The scan ID to resume
    :return: Empty result if success, 403 if the scan is not paused.
    """
    scan_info = get_scan_info_from_id(scan_id)
    if scan_info is None:
        abort(404, "Scan not found")

    core = _get_scan_core(scan_info)
    if not core.status.is_paused():
        abort(403, "Scan is not paused")

    core.pause(False)

    return jsonify({"message": "Success"})


@app.route("/scans/<int:scan_id>/stop", methods=["GET"])
@requires_auth
def scan_stop(scan_id):
    """
    Stop a scan

    :param scan_id: The scan ID to stop
    :return: Empty result if success, 403 if the current state indicates that
             the scan can't be stopped.
    """
    scan_info = get_scan_info_from_id(scan_id)
    if scan_info is None:
        abort(404, "Scan not found")

    core = _get_scan_core(scan_info)
    if not core.can_stop():
        abort(403, "Scan can not be stop")

    t = Process(target=core.stop, name="ScanStopThread", args=())
    t.daemon = True
    t.start()

    return jsonify({"message": "Stopping scan"})


def _get_scan_core(scan_info: ScanInfo) -> w3afCore:
    core = scan_info.w3af_core
    if core is None:
        abort(400, "Scan state is invalid")
    return core
