"""Profiling configuration shared across core layers."""

import os


def _environment_flag_is_enabled(variable):
    value = os.environ.get(variable, "0")
    return value.isdigit() and int(value) == 1


def is_core_profiling_enabled():
    """Return whether core profiling is enabled by the environment."""
    return _environment_flag_is_enabled("W3AF_CORE_PROFILING")


def is_cpu_profiling_enabled():
    """Return whether CPU profiling is enabled by the environment."""
    return _environment_flag_is_enabled("W3AF_CPU_PROFILING")


def is_memory_profiling_enabled():
    """Return whether memory profiling is enabled by the environment."""
    return _environment_flag_is_enabled("W3AF_MEMORY_PROFILING")


def is_tracemalloc_enabled():
    """Return whether tracemalloc profiling is enabled by the environment."""
    return _environment_flag_is_enabled("W3AF_PYTRACEMALLOC")
