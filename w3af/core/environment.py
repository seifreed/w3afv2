"""Environment checks shared across core layers."""

import os


def is_running_on_ci():
    """Return whether the process is running on CircleCI."""
    return os.environ.get("CIRCLECI", "false") == "true"
