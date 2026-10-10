"""
helper_script.py

Copyright 2013 Andres Riancho

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

SCRIPT_NAME = "w3af_dependency_install.sh"


def generate_helper_script(
    directory,
    pkg_manager_cmd,
    os_packages,
    pip_cmd,
    failed_deps,
    external_commands,
    in_virtualenv,
):
    """
    Generates a helper script to be run by the user to install all the
    dependencies.

    :param directory: Where the script is written
    :param in_virtualenv: True if pip installs inside a virtualenv (no sudo)
    :return: The path to the script name.
    """
    script_path = os.path.join(directory, SCRIPT_NAME)

    with open(script_path, "w") as script_file:
        script_file.write("#!/bin/bash\n")

        #
        #    Report the missing system packages
        #
        if os_packages:
            missing_pkgs = " ".join(os_packages)
            script_file.write(f"{pkg_manager_cmd} {missing_pkgs}\n")

        #
        #    Report all missing python modules
        #
        if failed_deps:
            script_file.write("\n")

            if in_virtualenv:
                script_file.write("# Run without sudo to install inside venv\n")

            not_git_pkgs = [fdep for fdep in failed_deps if not fdep.is_git]
            git_pkgs = [fdep.git_src for fdep in failed_deps if fdep.is_git]

            if not_git_pkgs:
                cmd = generate_pip_install_non_git(pip_cmd, not_git_pkgs, in_virtualenv)
                script_file.write(f"{cmd}\n")

            for missing_git_pkg in git_pkgs:
                cmd = generate_pip_install_git(pip_cmd, missing_git_pkg, in_virtualenv)
                script_file.write(f"{cmd}\n")

        for cmd in external_commands:
            script_file.write(f"{cmd}\n")

    # Make it executable
    os.chmod(script_path, 0o700)

    return script_path


def generate_pip_install_non_git(pip_cmd, not_git_pkgs, in_virtualenv):
    cmd_fmt = "%s install %s" if in_virtualenv else "sudo %s install %s"

    install_specs = [
        f"{fdep.package_name}=={fdep.package_version}" for fdep in not_git_pkgs
    ]

    return cmd_fmt % (pip_cmd, " ".join(install_specs))


def generate_pip_install_git(pip_cmd, git_pkg, in_virtualenv):
    """
    :param pip_cmd: The pip command for this platform
    :param git_pkg: The name of the pip+git package
    :param in_virtualenv: True if pip installs inside a virtualenv (no sudo)
    :return: The command to be run to install the pip+git package
    """
    if in_virtualenv:
        cmd_fmt = "%s install --ignore-installed %s"
    else:
        cmd_fmt = "sudo %s install --ignore-installed %s"

    return cmd_fmt % (pip_cmd, git_pkg)
