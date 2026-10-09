"""
history.py

Copyright 2007 Andres Riancho

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

import operator
import os

import msgpack


class HistorySuggestion:
    """Handles the history of any text, providing suggestions.

    :param filename: Name of the file where the info is stored

    It's also responsible of loading and saving the info in a file.
    """

    def __init__(self, filename):
        # Where the history items will be stored
        self.filename = filename

        # dict: {text:points}
        self.history = {}

        if os.access(filename, os.R_OK):
            self.history = self._load()

    def _load(self):
        """Reads the msgpack history file, resetting it when it is broken."""
        try:
            with open(self.filename, "rb") as fileh:
                return msgpack.load(fileh, raw=False)
        except (OSError, ValueError, msgpack.UnpackException):
            self.history = {}
            self.save()
            return {}

    def get_texts(self):
        """Provides the texts, ordered by relevance.

        :return: a list with the texts
        """
        info = sorted(self.history.items(), key=operator.itemgetter(1), reverse=True)
        return [text for text, _points in info]

    def insert(self, newtext):
        """Inserts new text to the history."""
        self.history[newtext] = self.history.get(newtext, 0) + 1

    def save(self):
        """Saves the history information."""
        with open(self.filename, "wb") as fileh:
            msgpack.dump(self.history, fileh)
