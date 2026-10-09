"""
recording_output.py

Copyright 2026 w3af contributors

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

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.plugins.output_plugin import OutputPlugin
from w3af.core.data.constants import severity


class recording_output(OutputPlugin):
    """
    Output plugin which keeps every message it receives in memory, so tests
    can assert on what the framework logged through the output manager.
    """

    def __init__(self):
        OutputPlugin.__init__(self)
        self.messages = []

    def debug(self, message, new_line=True):
        self.messages.append(("debug", message))

    def information(self, message, new_line=True):
        self.messages.append(("information", message))

    def error(self, message, new_line=True):
        self.messages.append(("error", message))

    def vulnerability(self, message, new_line=True, severity=severity.MEDIUM):
        self.messages.append(("vulnerability", message))

    def console(self, message, new_line=True):
        self.messages.append(("console", message))

    def messages_of(self, kind):
        """
        :return: The messages of the given kind, after the output manager
                 processed every message that was queued before this call.
        """
        om.manager.process_all_messages()
        return [message for msg_kind, message in self.messages if msg_kind == kind]


def start_recording_output():
    """
    Registers a recording_output instance in the current output manager.

    :return: The recording_output instance
    """
    recorder = recording_output()
    om.manager.set_output_plugin_inst(recorder)
    return recorder
