"""
menu.py

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

from w3af.core.data.kb.vuln_templates.utils import (
    get_template_by_name,
    get_template_names,
)
from w3af.core.exceptions import BaseFrameworkException
from w3af.core.ui.console.config import ConfigMenu
from w3af.core.ui.console.menu import menu
from w3af.core.ui.console.util import suggest


class kbMenu(menu):
    """
    This menu is used to display information from the knowledge base
    and (in the nearest future) to manipulate it.

    :author: Alexander Berezhnoy (alexander.berezhnoy |at| gmail.com)
    """

    def __init__(self, name, console, w3afcore, parent=None, **other):
        menu.__init__(self, name, console, w3afcore, parent)
        self._load_help("kb")

        # A mapping of KB data types to how to display it.
        # Key of the data type => (KB getter, (column names), (column getters))k
        self.__getters = {
            "vulns": (
                self._w3af.knowledge_base.get_all_vulns,
                ["Vulnerability", "Description"],
            ),
            "info": (
                self._w3af.knowledge_base.get_all_infos,
                ["Info", "Description"],
            ),
            "shells": (
                self._w3af.knowledge_base.get_all_shells,
                ["Shells", "Description"],
            ),
        }

    def _list_objects(self, descriptor, objs):
        col_names = descriptor[0]
        result = [col_names]

        for obj in objs:
            result.append([])
            row = [obj.get_name(), obj.get_desc()]

            result.append(row)

        self._console.draw_table(result)

    def _cmd_list(self, params):
        if len(params) > 0:
            for p in params:
                if p in self.__getters:
                    desc = self.__getters[p]
                    self._list_objects(desc[1:], desc[0]())
                else:
                    self._output.console(f"Type {p} is unknown")
        else:
            self._output.console("Parameter type is missing, see the help:")
            self._cmd_help(["list"])

    def _para_list(self, params, part):
        if len(params):
            return []

        return suggest(list(self.__getters.keys()), part)

    def _cmd_add(self, params):
        if len(params) == 0:
            self._output.console('Parameter "type" is missing, see the help:')
            self._cmd_help(["add"])
            return

        if len(params) > 1:
            self._output.console("Only one parameter is accepted, see the help:")
            self._cmd_help(["add"])
            return

        template_name = params[0]
        if template_name not in get_template_names():
            self._output.console(f"Type {template_name} is unknown")
            return

        # Now we use the fact that templates are configurable just like
        # plugins, misc-settings, etc.
        template_inst = get_template_by_name(template_name)
        template_menu = StoreOnBackConfigMenu(
            template_name,
            self._console,
            self._w3af,
            self,
            template_inst,
            self._w3af.knowledge_base,
        )

        # Note: The data is stored in the KB when the user does a "back"
        #       see the StoreOnBackConfigMenu implementation
        return template_menu

    def _para_add(self, params, part):
        if len(params):
            return []

        return suggest(get_template_names(), part)


class StoreOnBackConfigMenu(ConfigMenu):
    def __init__(self, name, console, w3af, parent, configurable, knowledge_base):
        super().__init__(name, console, w3af, parent, configurable)
        self._knowledge_base = knowledge_base

    def _cmd_back(self, tokens):
        try:
            self._cmd_save(tokens)
        except (ValueError, BaseFrameworkException) as e:
            self._output.error(str(e))
            return self._console.back

        # The template validates its configuration when it is saved
        self._configurable.store_in_kb(self._knowledge_base)
        vuln_name = self._configurable.get_vulnerability_name()
        self._output.console(f'Stored "{vuln_name}" in the knowledge base.')

        return self._console.back
