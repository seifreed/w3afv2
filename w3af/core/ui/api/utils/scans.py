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

import logging
import os
import tempfile
from itertools import count

from w3af.core.ui.api.db.master import SCANS, ScanInfo

PROFILE_EXTENSION = ".pw3af"
PROFILE_ENCODING = "utf-8"

logger = logging.getLogger(__name__)
_scan_ids = count()


def get_scan_info_from_id(scan_id: int) -> ScanInfo | None:
    return SCANS.get(scan_id, None)


def get_new_scan_id() -> int:
    return next(_scan_ids)


def create_temp_profile(scan_profile: str) -> tuple[str, str]:
    """
    Writes the scan_profile to a file

    :param scan_profile: The contents of a profile configuration
    :return: The scan profile file name and the directory where it was created
    """
    descriptor, scan_profile_file = tempfile.mkstemp(suffix=PROFILE_EXTENSION)
    with os.fdopen(descriptor, "w", encoding=PROFILE_ENCODING) as profile_file:
        profile_file.write(scan_profile)

    return scan_profile_file, os.path.dirname(scan_profile_file)


def remove_temp_profile(scan_profile_file_name: str) -> None:
    """
    Remove temp profile after using
    :param scan_profile_file_name: path to the temp profile
    :return: None
    """
    try:
        os.remove(scan_profile_file_name)
    except OSError:
        logger.debug("Temporary profile %s was already removed", scan_profile_file_name)


def start_scan_helper(scan_info: ScanInfo) -> None:
    """
    Start scan from scan_info

    :param scan_info: ScanInfo object contains initialized w3afCore
    """
    w3af_core = scan_info.w3af_core
    try:
        # Init plugins!
        w3af_core.plugins.init_plugins()

        # Clear all current output plugins
        # Add the REST API output plugin
        w3af_core._output_manager.set_output_plugins([])
        w3af_core._output_manager.set_output_plugin_inst(scan_info.output)

        # Start the scan!
        w3af_core.verify_environment()
        w3af_core.start()
    except Exception as e:
        logger.exception("The scan finished with an unhandled exception")
        scan_info.exception = e
        w3af_core.stop()

    finally:
        scan_info.finished = True
        remove_temp_profile(scan_info.profile_path)
