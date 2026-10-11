"""
text_file_log.py

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

import os
import tempfile
from contextlib import contextmanager

import w3af.core.controllers.output_manager as om
from w3af.core.data.options.output_file_option import DEV_NULL
from w3af.plugins.output.text_file import text_file


class TextFileLog:
    """
    Records the messages sent to the output manager using the text_file output
    plugin, writing to a temporary file which tests can inspect.
    """

    PLUGIN_NAME = "text_file"

    def __init__(self):
        file_descriptor, self.path = tempfile.mkstemp(prefix="w3af-test-log-")
        os.close(file_descriptor)

    def remove(self):
        os.unlink(self.path)

    def plugin_options(self):
        """
        :return: The (name, value, type) option tuples that configure the
                 text_file output plugin to write into this log
        """
        return (
            ("output_file", self.path, "output_file"),
            ("http_output_file", DEV_NULL, "output_file"),
            ("verbose", False, "boolean"),
        )

    @contextmanager
    def attached_to_output_manager(self):
        """
        Send the output manager messages to this log while the context is
        active, for code which runs outside of a scan.
        """
        plugin = text_file()
        options = plugin.get_options()
        for name, value, _ in self.plugin_options():
            options[name].set_value(value)
        plugin.set_options(options)

        output_manager = om._get_default_manager()
        output_manager.set_output_plugin_inst(plugin)
        try:
            yield self
        finally:
            output_manager.process_all_messages()
            output_manager.get_output_plugin_inst().remove(plugin)
            plugin.end()

    def contains(self, log_type, message):
        """
        :return: True if a message of log_type was written to the log
        """
        escaped_message = repr(message)[1:-1]
        suffix = f" - {log_type}] {escaped_message}"

        with open(self.path) as log_file:
            return any(line.rstrip("\n").endswith(suffix) for line in log_file)
