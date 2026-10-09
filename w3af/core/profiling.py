"""Profiling configuration shared across core layers."""

import os


def is_core_profiling_enabled():
    """Return whether core profiling is enabled by the environment."""
    env_value = os.environ.get("W3AF_CORE_PROFILING", "0")
    return env_value.isdigit() and int(env_value) == 1
