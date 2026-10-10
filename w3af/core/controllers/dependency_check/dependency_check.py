"""
dependency_check.py

Copyright 2006 Andres Riancho

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

import json
import logging
import sys
import warnings
from importlib.metadata import distributions
from importlib.util import find_spec

from packaging.utils import canonicalize_name
from packaging.version import Version

from w3af.core.controllers.dependency_check.helper_requirements_txt import (
    generate_requirements_txt,
)
from w3af.core.controllers.dependency_check.helper_script import (
    generate_helper_script,
    generate_pip_install_git,
    generate_pip_install_non_git,
)
from w3af.core.controllers.dependency_check.platforms.base_platform import CORE
from w3af.core.controllers.dependency_check.platforms.current_platform import (
    get_current_platform,
)
from w3af.core.controllers.dependency_check.utils import verify_python_version
from w3af.core.data.db.startup_cfg import StartUpConfig

verify_python_version()

if find_spec("pip") is None:
    print("We recommend you install pip before continuing.")
    print("http://www.pip-installer.org/en/latest/installing.html")
    sys.exit(1)


def get_missing_pip_packages(platform, dependency_set):
    """
    Check for missing python modules
    """
    failed_deps = []

    for w3af_req in platform.PIP_PACKAGES[dependency_set]:

        for dist in distributions():
            dist_name = dist.metadata.get("Name", "")
            if canonicalize_name(w3af_req.package_name) == canonicalize_name(dist_name):
                if w3af_req.is_git:
                    direct_url_json = dist.read_text("direct_url.json")
                    if direct_url_json is None:
                        continue

                    direct_url = json.loads(direct_url_json)
                    installed_commit = direct_url.get("vcs_info", {}).get("commit_id")
                    if installed_commit == w3af_req.package_version:
                        break
                    continue

                w3af_req_version = str(Version(w3af_req.package_version))
                dist_version = str(Version(dist.version))

                if w3af_req_version == dist_version:
                    # It's installed and the version matches!
                    break
        else:
            failed_deps.append(w3af_req)

    return failed_deps


def get_missing_os_packages(platform, dependency_set):
    """
    Check for missing operating system packages
    """
    missing_os_packages = []

    for os_package in platform.SYSTEM_PACKAGES[dependency_set]:
        if not platform.os_package_is_installed(os_package):
            missing_os_packages.append(os_package)

    return list(set(missing_os_packages))


def get_missing_external_commands(platform):
    """
    Check for missing external commands such as "retire" which is used
    by the retirejs grep plugin.

    :param platform: Current platform
    :return: A list with commands to be run to install the missing external commands
    """
    return platform.get_missing_external_commands()


def write_instructions_to_console(
    platform, failed_deps, os_packages, script_path, external_commands
):
    #
    #    Report the missing system packages
    #
    msg = (
        "w3af's requirements are not met, one or more third-party"
        " libraries need to be installed.\n\n"
    )

    if os_packages:
        missing_pkgs = " ".join(os_packages)

        msg += (
            "On %s systems please install the following operating"
            " system packages before running the pip installer:\n"
            "    %s %s\n"
        )
        print(msg % (platform.SYSTEM_NAME, platform.PKG_MANAGER_CMD, missing_pkgs))

    #
    #    Report all missing python modules
    #
    if failed_deps:
        msg = "Your python installation needs the following modules" " to run w3af:\n"
        msg += "    " + " ".join([fdep.module_name for fdep in failed_deps])
        print(msg)
        print("\n")

        #
        #    Report missing pip packages
        #
        not_git_pkgs = [fdep for fdep in failed_deps if not fdep.is_git]
        git_pkgs = [fdep.git_src for fdep in failed_deps if fdep.is_git]

        msg = (
            "After installing any missing operating system packages, use"
            " pip to install the remaining modules:\n"
        )

        if not_git_pkgs:
            cmd = generate_pip_install_non_git(platform.PIP_CMD, not_git_pkgs)
            msg += f"    {cmd}\n"

        if git_pkgs:
            for missing_git_pkg in git_pkgs:
                install_command = generate_pip_install_git(
                    platform.PIP_CMD, missing_git_pkg
                )
                msg += f"    {install_command}\n"

        print(msg)

    if external_commands:
        print(
            "External programs used by w3af are not installed or were not found."
            "Run these commands to install them on your system:\n"
        )
        for cmd in external_commands:
            print(f"    {cmd}")

        print()

    platform.after_hook()

    msg = "A script with these commands has been created for you at %s"
    print(msg % script_path)


def dependency_check(dependency_set=CORE, exit_on_failure=True, platform=None):
    """
    This function verifies that the dependencies that are needed by the
    framework core are met.

    :param platform: The platform to check, defaults to the current one
    :return: True if the process should exit
    """
    if StartUpConfig().get_skip_dependencies_check():
        return False

    disable_warnings()

    if platform is None:
        platform = get_current_platform()

    failed_deps = get_missing_pip_packages(platform, dependency_set)
    os_packages = get_missing_os_packages(platform, dependency_set)
    external_commands = get_missing_external_commands(platform)

    enable_warnings()

    # If everything is installed, just exit
    if not failed_deps and not os_packages and not external_commands:
        # False means: do not exit()
        return False

    generate_requirements_txt(failed_deps)

    script_path = generate_helper_script(
        platform.PKG_MANAGER_CMD,
        os_packages,
        platform.PIP_CMD,
        failed_deps,
        external_commands,
    )

    write_instructions_to_console(
        platform, failed_deps, os_packages, script_path, external_commands
    )

    if exit_on_failure:
        sys.exit(1)
    else:
        return True


def disable_warnings():
    warnings.filterwarnings(
        "ignore",
        ".*",
    )

    # scapy raises an error if tcpdump is not found in PATH
    logging.disable(logging.CRITICAL)


def enable_warnings():
    # Enable warnings once again
    warnings.resetwarnings()

    # re-enable the logging module
    logging.disable(logging.NOTSET)
