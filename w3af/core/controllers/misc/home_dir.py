"""
home_dir.py

Copyright 2008 Andres Riancho

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

import os
import shutil
import sys

from w3af import ROOT_PATH
from w3af.core.paths import get_home_dir as _get_home_dir

# Point to the directory where w3af_console , w3af_gui and profiles/ live
# Also, the root of the git repository
W3AF_LOCAL_PATH = os.sep.join(__file__.split(os.sep)[:-5]) + os.path.sep


# I need to check in different paths to support installing w3af as a module.
# Note the gen_data_files.py code in the w3af-module.
DEFAULT_PROFILES_PATHS = (
    os.path.join(W3AF_LOCAL_PATH, "profiles"),
    os.path.join(ROOT_PATH, "profiles"),
    os.path.join(ROOT_PATH, "../profiles"),
    os.path.join(sys.prefix, "profiles"),
    os.path.join(sys.exec_prefix, "profiles"),
    # https://github.com/andresriancho/w3af-module/issues/4
    os.path.join(sys.prefix, "local", "profiles"),
    os.path.join(sys.exec_prefix, "local", "profiles"),
)


def create_home_dir():
    """
    Creates the w3af home directory, on linux: /home/user/.w3af/
    :return: True if success.
    """
    home_path = _get_home_dir()

    # The home directory, the webroot for some plugins and the profiles
    return (
        ensure_dir(home_path)
        and ensure_dir(os.path.join(home_path, "webroot"))
        and copy_default_profiles(os.path.join(home_path, "profiles"))
    )


def ensure_dir(path):
    """
    :return: True if the directory exists or was created
    """
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        # Handle some really strange cases where there is a race-condition
        # where multiple w3af processes are starting and creating the same
        # directory
        #
        # https://circleci.com/gh/andresriancho/w3af/1347
        return os.path.isdir(path)

    return True


def copy_default_profiles(home_profiles, candidates=DEFAULT_PROFILES_PATHS):
    """
    Copy the first existing directory in candidates to home_profiles, unless
    home_profiles already exists.

    :return: True if home_profiles exists after the call
    """
    if os.path.exists(home_profiles):
        return True

    for default_profile_path in candidates:
        if not os.path.exists(default_profile_path):
            continue

        try:
            shutil.copytree(default_profile_path, home_profiles)
        except OSError:
            return False

        return True

    return False


def verify_dir_has_perm(path, perm, levels=0):
    """
    Verify that home directory has `perm` access for current user. If at
    least one of them fails to have it the result will be False.

    :param path: Path to test
    :param perm: Access rights. Possible values are os' R_OK, W_OK and X_OK or
        the result of a bitwise "|" operator applied a combination of them.
    :param levels: Depth levels to test
    """
    if not os.path.exists(path):
        raise RuntimeError(f"{path} does NOT exist!")

    path = os.path.normpath(path)
    pdepth = len(path.split(os.path.sep))

    pathaccess = os.access(path, perm)

    # 0th level
    if not levels or not pathaccess:
        return pathaccess

    # From 1st to `levels`th
    for root, dirs, files in os.walk(path):
        currentlevel = len(root.split(os.path.sep)) - pdepth

        if currentlevel > levels:
            break
        elif ".git" in dirs:
            dirs.remove(".git")

        for file_path in (os.path.join(root, f) for f in dirs + files):
            if os.path.exists(file_path) and not os.access(file_path, perm):
                return False
    return True
