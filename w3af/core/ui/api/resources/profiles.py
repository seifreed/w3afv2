"""
profiles.py

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

from typing import Any

from flask import Response, jsonify, request

from w3af.core.controllers.core_helpers.profiles import CoreProfiles
from w3af.core.controllers.misc.home_dir import create_home_dir
from w3af.core.data.profile.profile import profile as Profile
from w3af.core.ui.api.application import app
from w3af.core.ui.api.resources.plugins import plugin_catalog, plugin_exists
from w3af.core.ui.api.utils.auth import requires_auth
from w3af.core.ui.api.utils.error import abort
from w3af.core.ui.api.utils.profile_composer import compose_profile

PROFILE_ENCODING = "utf-8"


def load_profiles() -> list[Profile]:
    """
    :return: The valid profiles stored in the w3af home directory, sorted by name
    """
    create_home_dir()
    valid_profiles, _ = CoreProfiles(None).get_profile_list()
    return sorted(valid_profiles, key=lambda profile: profile.get_name().lower())


def find_profile(profile_name: str) -> Profile | None:
    for profile in load_profiles():
        if profile.get_name() == profile_name:
            return profile
    return None


@app.route("/profiles/", methods=["GET"])
@requires_auth
def list_profiles() -> Response:
    """
    :return: A JSON containing a list of the available profiles, with:
        - The profile resource URL (eg. /profiles/fast_scan)
        - The profile name
        - The profile description
    """
    return jsonify({"items": [profile_to_json(p) for p in load_profiles()]})


@app.route("/profiles/<profile_name>", methods=["GET"])
@requires_auth
def get_profile(profile_name: str) -> Response:
    """
    :return: The profile information, its contents (which can be sent as the
             scan_profile when starting a scan) and the enabled plugins
    """
    profile = find_profile(profile_name)
    if profile is None:
        abort(404, "Profile not found")

    return jsonify(profile_to_json(profile, detailed=True))


@app.route("/profiles/compose", methods=["POST"])
@requires_auth
def compose() -> Response:
    """
    Receive a JSON containing:
        - scan_profile: The contents of a profile (optional, can be empty)
        - plugins: The plugin names to enable, keyed by plugin type

    :return: A JSON containing the scan_profile with exactly those plugins
             enabled, ready to be used to start a new scan
    """
    payload = request.get_json()
    if not isinstance(payload, dict):
        abort(400, "Expected a JSON object")

    scan_profile = payload.get("scan_profile", "")
    if not isinstance(scan_profile, str):
        abort(400, "Expected scan_profile to be a string")

    plugins = validate_plugin_selection(payload.get("plugins"))

    return jsonify({"scan_profile": compose_profile(scan_profile, plugins)})


def validate_plugin_selection(selection: Any) -> dict[str, list[str]]:
    """
    :param selection: The user provided plugin names keyed by plugin type
    :return: The selection, if all the plugin types and names exist
    """
    if not isinstance(selection, dict):
        abort(400, "Expected plugins to be an object keyed by plugin type")

    catalog = plugin_catalog()

    plugin_types = catalog.get_plugin_types()

    for plugin_type, plugin_names in selection.items():
        if plugin_type not in plugin_types:
            abort(400, f'Unknown plugin type: "{plugin_type}"')

        if not isinstance(plugin_names, list):
            abort(400, f'Expected a list of plugin names for "{plugin_type}"')

        for plugin_name in plugin_names:
            if not isinstance(plugin_name, str) or not plugin_exists(
                catalog, plugin_type, plugin_name
            ):
                abort(400, f'Unknown plugin: "{plugin_type}.{plugin_name}"')

    return selection


def profile_to_json(profile: Profile, detailed: bool = False) -> dict[str, Any]:
    name = profile.get_name()
    summary: dict[str, Any] = {
        "name": name,
        "description": profile.get_desc(),
        "href": f"/profiles/{name}",
    }

    if detailed:
        with open(profile.get_profile_file(), encoding=PROFILE_ENCODING) as handle:
            summary["content"] = handle.read()

        summary["plugins"] = {
            plugin_type: profile.get_enabled_plugins(plugin_type)
            for plugin_type in sorted(plugin_catalog().get_plugin_types())
        }

    return summary
