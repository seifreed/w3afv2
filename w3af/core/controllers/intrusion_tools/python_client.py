"""Select and load the Python 3 clients sent to compromised hosts."""

from collections.abc import Callable
from pathlib import Path

from w3af import ROOT_PATH
from w3af.core.exceptions import BaseFrameworkException

CLIENT_PATH = (
    Path(ROOT_PATH)
    / "core"
    / "controllers"
    / "w3afAgent"
    / "client"
    / "w3af_agent_client.py"
)
EXTRUSION_CLIENT_PATH = (
    Path(ROOT_PATH)
    / "core"
    / "controllers"
    / "extrusion_scanning"
    / "client"
    / "extrusion_client.py"
)


def get_python3_client(
    exec_method: Callable[[str], str], client_path: Path
) -> tuple[str, str, str]:
    """Return a Python 3 interpreter and the requested client source."""
    for interpreter in ("python3", "python"):
        try:
            version = exec_method(
                f'{interpreter} -c "import sys; print(sys.version_info[0])"'
            )
        except BaseFrameworkException:
            continue

        if version.strip() == "3":
            return interpreter, client_path.read_text(), "py"

    raise BaseFrameworkException(
        "Failed to find a suitable Python 3 client for the remote system."
    )
