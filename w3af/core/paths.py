import os

HOME_DIR = os.path.join(os.path.expanduser("~"), ".w3af")


def get_home_dir():
    """Return the configured per-user w3af directory."""
    return os.environ.get("W3AF_HOME_DIR", HOME_DIR)
