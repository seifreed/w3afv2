"""
helpers.py

Copyright 2012 Andres Riancho

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

import copy
import io
import platform
import pprint
import sys
from itertools import chain

from w3af.core.controllers.misc.get_w3af_version import get_w3af_version


def pprint_plugins(w3af_core):
    # Return a pretty-printed string from the plugins dicts
    plugs_opts = copy.deepcopy(w3af_core.plugins.get_all_plugin_options())
    plugs = w3af_core.plugins.get_all_enabled_plugins()

    for ptype, plugin_list in plugs.items():
        for plugin in plugin_list:
            if plugin not in chain(*(list(pt.keys()) for pt in plugs_opts.values())):
                plugs_opts[ptype][plugin] = {}

    if not any(plugs_opts.values()):
        # No plugins configured, we return an empty string so the users of
        # this function understand that there is no config
        return ""

    plugins = io.StringIO()
    pprint.pprint(plugs_opts, plugins)
    return plugins.getvalue()


def get_platform_dist():
    """
    :return: A human-readable operating system name and release.
    """
    if platform.system() == "Linux":
        try:
            release = platform.freedesktop_os_release()
        except OSError:
            return "Unknown"

        values = (release.get("NAME", ""), release.get("VERSION_ID", ""))
    else:
        values = (platform.system(), platform.release())

    return " ".join(value for value in values if value) or "Unknown"


def get_versions():
    """
    :return: A string containing the python, platform and w3af versions
    """
    w3af_version = "\n    ".join(get_w3af_version().split("\n"))
    python_version = sys.version.replace("\n", "")

    return (
        f"  Python version: {python_version}\n"
        f"  Platform: {get_platform_dist()}\n"
        f"  w3af version:\n    {w3af_version}"
    )
