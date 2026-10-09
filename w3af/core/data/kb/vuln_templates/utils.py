"""
utils.py

Copyright 2013 Andres Riancho

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

from w3af import ROOT_PATH
from w3af.core.data.kb.vuln_templates.base_template import BaseTemplate


def get_all_templates():
    """
    :return: A list with instances of all available templates
    """
    templates = []
    location = [ROOT_PATH, "core", "data", "kb", "vuln_templates"]
    template_path = os.path.join(*location)

    for fname in os.listdir(template_path):
        if not fname.endswith("_template.py"):
            continue

        if fname == "base_template.py":
            continue

        fname = fname.replace(".py", "")

        # Please read help(__import__) to understand why I have to set
        # fromlist to something that's not empty.
        module_name = f"w3af.core.data.kb.vuln_templates.{fname}"
        module = __import__(
            module_name,
            fromlist=[
                None,
            ],
        )

        klasses = dir(module)
        for kls_name in klasses:

            kls = getattr(module, kls_name)

            if not isinstance(kls, type):
                continue

            if issubclass(kls, BaseTemplate) and kls is not BaseTemplate:
                template = kls()
                templates.append(template)

    return templates


def get_template_by_name(name):
    for template in get_all_templates():
        if template.get_short_name() == name:
            return template

    raise ValueError(f'Unknown template name "{name}".')


def get_template_names():
    templates = get_all_templates()
    template_names = [t.get_short_name() for t in templates]
    return template_names


def get_template_long_names():
    templates = get_all_templates()
    template_names = [t.get_vulnerability_name() for t in templates]
    return template_names
