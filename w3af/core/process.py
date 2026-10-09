"""Process-level runtime helpers shared across core layers."""

import multiprocessing


def is_main_process():
    """Return whether this code runs in the main process."""
    return multiprocessing.current_process().name == "MainProcess"
