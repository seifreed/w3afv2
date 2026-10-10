"""
auto_update.py

Copyright 2008 Andres Riancho

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

from w3af.core.controllers.auto_update.ui_wrapper import UIUpdater


def ask(msg):
    return input(msg + " [y/N] ").lower() in ("y", "yes")


class ConsoleUIUpdater(UIUpdater):

    def __init__(self, force, output):
        self._output = output
        UIUpdater.__init__(self, force=force, ask=ask, logger=self._output.console)

        # Show revisions logs function
        def show_log(msg, get_logs):
            if ask(msg):
                self._output.console(get_logs())

        # Add callbacks
        self._add_callback("callback_onupdate_confirm", ask)
        self._add_callback("callback_onupdate_show_log", show_log)

    def _handle_update_output(self, upd_output):
        # Nothing special to do here.
        pass
