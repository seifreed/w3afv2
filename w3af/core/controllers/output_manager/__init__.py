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

import atexit
from typing import TYPE_CHECKING

from .log_sink import LogSink
from .logging_bridge import remove_data_logging
from .manager import OutputManager

if TYPE_CHECKING:
    manager: OutputManager
    out: LogSink


def create_output_manager() -> tuple[OutputManager, LogSink]:
    """Create an independently owned output manager and sink."""
    output_manager = OutputManager()
    output_manager.start()
    output = LogSink(output_manager.get_in_queue())
    output_manager.set_output(output)
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

    log_sink_factory(new_manager.get_in_queue())
    return new_manager


def log_sink_factory(om_queue):
    """
    Creates a new "out" instance at the module level.

    :return: A reference to the newly created instance
    """
    global _out

    output = LogSink(om_queue)
    _out = output
    globals()["out"] = output
    return output


def _get_default_manager() -> OutputManager:
    global _manager

    explicit_manager = globals().get("manager")
    if explicit_manager is not None and explicit_manager.is_alive():
        _manager = explicit_manager
    elif _manager is None or not _manager.is_alive():
        _manager = OutputManager()
        _manager.start()

    globals()["manager"] = _manager

    explicit_output = globals().get("out")
    if explicit_output is not None and (
        explicit_output._closed
        or explicit_output.om_queue is not _manager.get_in_queue()
    ):
        log_sink_factory(_manager.get_in_queue())

    return _manager


def _get_default_output() -> LogSink:
    global _out

    manager = _get_default_manager()
    explicit_output = globals().get("out")
    if (
        explicit_output is not None
        and not explicit_output._closed
        and explicit_output.om_queue is manager.get_in_queue()
    ):
        _out = explicit_output
        return explicit_output

    if _out is None or _out._closed or _out.om_queue is not manager.get_in_queue():
        _out = LogSink(manager.get_in_queue())

    globals()["out"] = _out
    return _out


def close_default_output_manager() -> None:
    """Stop and forget the process-level output manager, if any."""
    global _manager, _out

    output = globals().pop("out", None) or _out
    _out = None
    if output is not None:
        output.close()
        remove_data_logging(output)

    manager = globals().pop("manager", None) or _manager
    if manager is not None:
        manager.stop()

    _manager = None


def __getattr__(name):
    if name == "manager":
        return _get_default_manager()
    if name == "out":
        return _get_default_output()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_manager: OutputManager | None = None
_out: LogSink | None = None
atexit.register(close_default_output_manager)

# The import machinery exposes the child module as ``manager`` on this package.
# Remove that name so module attribute access reaches the lazy provider above.
globals().pop("manager", None)
