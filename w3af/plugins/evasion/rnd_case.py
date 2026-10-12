"""
rnd_case.py

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

from secrets import randbelow

from w3af.core.controllers.plugins.evasion_plugin import EvasionPlugin


class rnd_case(EvasionPlugin):
    """
    Change the case of random letters.
    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    def modify_request(self, request):
        return self._modify_request_with_mutator(request, self._mutate)

    def _mutate(self, data):
        """
        Change the case of the data string.
        :return: a string.
        """
        new_data = ""
        for char in data:
            if randbelow(2) == 1:
                char = char.upper()
            else:
                char = char.lower()
            new_data += char
        return new_data

    def get_priority(self):
        """
        This function is called when sorting evasion plugins.
        Each evasion plugin should implement this.

        :return: An integer specifying the priority. 100 is run first, 0 last.
        """
        return 25

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        return """
        This evasion plugin changes the case of random letters.

        Example:
            Input:      '/bar/foo.asp'
            Output:     '/BAr/foO.Asp'
        """
