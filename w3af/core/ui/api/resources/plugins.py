"""
plugins.py

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

from textwrap import dedent
from typing import Any

from flask import Response, jsonify

from w3af.core.controllers.core_helpers.plugin_catalog import PluginCatalog
from w3af.core.data.db.dbms import database_session
from w3af.core.ui.api.application import app
from w3af.core.ui.api.utils.auth import requires_auth
from w3af.core.ui.api.utils.error import abort


def plugin_catalog() -> PluginCatalog:
    """
    :return: The plugin manager used to query the available plugins; it is not
             attached to any scan
    """
    return PluginCatalog()


def plugin_exists(catalog: PluginCatalog, plugin_type: str, plugin_name: str) -> bool:
    return plugin_type in catalog.get_plugin_types() and (
        plugin_name in catalog.get_plugin_list(plugin_type)
    )


@app.route("/plugins/", methods=["GET"])
@requires_auth
def list_plugins() -> Response:
    """
    :return: A JSON containing a list of plugin types, each one with:
        - The plugin type (eg. audit)
        - The plugin type description
        - The names of the plugins of that type
    """
    catalog = plugin_catalog()
    items = [
        plugin_type_to_json(catalog, plugin_type)
        for plugin_type in sorted(catalog.get_plugin_types())
    ]
    return jsonify({"items": items})


@app.route("/plugins/<plugin_type>/<plugin_name>", methods=["GET"])
@requires_auth
def get_plugin(plugin_type: str, plugin_name: str) -> Response:
    """
    :return: The plugin descriptions and its configurable options
    """
    catalog = plugin_catalog()
    if not plugin_exists(catalog, plugin_type, plugin_name):
        abort(404, "Plugin not found")

    with database_session() as database:
        plugin = catalog.get_quick_instance(plugin_type, plugin_name, database)

        return jsonify(
            {
                "type": plugin_type,
                "name": plugin_name,
                "description": plugin.get_desc(),
                "long_description": dedent(plugin.get_long_desc()).strip(),
                "options": [option_to_json(option) for option in plugin.get_options()],
            }
        )


def plugin_type_to_json(catalog: PluginCatalog, plugin_type: str) -> dict[str, Any]:
    return {
        "type": plugin_type,
        "description": catalog.get_plugin_type_desc(plugin_type).strip(),
        "plugins": catalog.get_plugin_list(plugin_type),
    }


def option_to_json(option: Any) -> dict[str, str]:
    """
    :param option: A w3af plugin option
    :return: The option serialized as strings, as it is written in profiles
    """
    return {
        "name": option.get_name(),
        "type": option.get_type(),
        "value": option.get_value_str(),
        "description": option.get_desc(),
        "help": option.get_help(),
    }
