"""Ask the operating system's package manager if a package is installed."""

from w3af.core.controllers.misc.external_process import run_process


def query_package(command, package_name, classify_output):
    """
    :param command: Program and arguments that report a package status, the
                    package name is appended to them
    :param package_name: The operating system package to look for
    :param classify_output: Function receiving the command output and the
                            package name that returns True / False when the
                            package is / is not installed, None if unknown
    :return: True if installed, False if not installed, None when the package
             manager is not available or its answer is not understood
    """
    try:
        result = run_process([*command, package_name])
    except OSError:
        return None

    return classify_output(result.stdout, package_name)
