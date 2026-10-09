"""
profile_composer.py

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

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

SECTION_HEADER = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")
PROFILE_SECTION = "profile"
DEFAULT_PROFILE_HEADER = [
    "[profile]",
    "name = web_ui",
    "description = Scan profile composed in the w3af web user interface",
]


@dataclass
class Section:
    name: str | None
    lines: list[str] = field(default_factory=list)


def split_sections(profile_text: str) -> list[Section]:
    """
    :return: The profile split in INI sections. Lines before the first header
             are kept in a section without name.
    """
    sections = [Section(name=None)]

    for line in profile_text.splitlines():
        header = SECTION_HEADER.match(line)
        if header:
            sections.append(Section(name=header.group("name").strip()))
        sections[-1].lines.append(line)

    return sections


def plugin_section_name(plugin_type: str, plugin_name: str) -> str:
    return f"{plugin_type}.{plugin_name}"


def is_disabled_plugin(section: Section, enabled: set[str], types: set[str]) -> bool:
    """
    :return: True if the section configures a plugin of one of the managed
             types which is not enabled anymore
    """
    if section.name is None or "." not in section.name:
        return False

    plugin_type = section.name.split(".", 1)[0]
    return plugin_type in types and section.name not in enabled


def compose_profile(
    profile_text: str, enabled_plugins: Mapping[str, Sequence[str]]
) -> str:
    """
    Enable exactly the given plugins for each plugin type in enabled_plugins,
    keeping the existing plugin options and every other profile setting.

    :param profile_text: The contents of a w3af profile, can be empty
    :param enabled_plugins: Plugin names to enable, keyed by plugin type. Types
                            which are not present are left untouched.
    :return: The contents of the composed profile
    """
    managed_types = set(enabled_plugins)
    enabled = {
        plugin_section_name(plugin_type, plugin_name)
        for plugin_type, plugin_names in enabled_plugins.items()
        for plugin_name in plugin_names
    }

    sections = [
        section
        for section in split_sections(profile_text)
        if not is_disabled_plugin(section, enabled, managed_types)
    ]
    existing = {section.name for section in sections}

    if PROFILE_SECTION not in existing:
        profile_header = list(DEFAULT_PROFILE_HEADER)
        sections.insert(1, Section(name=PROFILE_SECTION, lines=profile_header))

    sections.extend(
        Section(name=name, lines=["", f"[{name}]"])
        for name in sorted(enabled - existing)
    )

    lines = [line for section in sections for line in section.lines]
    return "\n".join(lines).strip("\n") + "\n"
