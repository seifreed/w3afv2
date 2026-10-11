"""
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

from .log_sink import LogSink
from .manager import OutputManager


def create_output_manager() -> tuple[OutputManager, LogSink]:
    """Create an independently owned output manager and sink."""
    output_manager = OutputManager()
    output_manager.start()
    output = LogSink(output_manager.get_in_queue())
    return output_manager, output


def fresh_output_manager_inst():
    """
    Creates a new "manager" instance at the module level.

    :return: A reference to the newly created instance
    """
    global _manager

    has_explicit_manager = "manager" in globals()
    old_manager = globals().get("manager", _manager)
    if old_manager is not None:
        old_manager.stop()

    new_manager = OutputManager()
    new_manager.start()
    if has_explicit_manager:
        globals()["manager"] = new_manager
    else:
        _manager = new_manager
    return new_manager


def log_sink_factory(om_queue):
    """
    Creates a new "out" instance at the module level.

    :return: A reference to the newly created instance
    """
    output = LogSink(om_queue)
    globals()["out"] = output
    return output


def _get_default_manager() -> OutputManager:
    global _manager
    if _manager is None:
        _manager = OutputManager()
    return _manager


def _get_default_output() -> LogSink:
    global _out
    if _out is None:
        _out = LogSink(_get_default_manager().get_in_queue())
    return _out


def __getattr__(name):
    if name == "manager":
        return _get_default_manager()
    if name == "out":
        return _get_default_output()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_manager: OutputManager | None = None
_out: LogSink | None = None

# The import machinery exposes the child module as ``manager`` on this package.
# Remove that name so module attribute access reaches the lazy provider above.
globals().pop("manager", None)
