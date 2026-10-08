"""
requirements.py

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

import sys
from pathlib import Path

from packaging.requirements import Requirement

from w3af.core.controllers.dependency_check.pip_dependency import PIPDependency

CORE = 1
GUI = 2

PROJECT_ROOT = Path(__file__).resolve().parents[4]
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"


def _normalize_package_name(package_name):
    return package_name.lower().replace("_", "-")


def _load_pinned_packages():
    versions = {}
    sources = {}

    with REQUIREMENTS_FILE.open(encoding="utf-8") as requirements:
        for raw_line in requirements:
            line = raw_line.partition("#")[0].strip()
            if not line:
                continue

            requirement = Requirement(line)
            package_key = _normalize_package_name(requirement.name)
            if requirement.url:
                sources[package_key] = requirement.url
                versions[package_key] = requirement.url.rsplit("@", 1)[-1]
                continue

            for specifier in requirement.specifier:
                if specifier.operator == "==":
                    versions[package_key] = specifier.version
                    break

    return versions, sources


PINNED_VERSIONS, PINNED_SOURCES = _load_pinned_packages()


def _version(package_name):
    package_key = _normalize_package_name(package_name)
    try:
        return PINNED_VERSIONS[package_key]
    except KeyError as key_error:
        raise RuntimeError(
            f"{package_name} must be pinned in {REQUIREMENTS_FILE}"
        ) from key_error


CORE_PIP_PACKAGES = [
    PIPDependency("pyclamd", "pyClamd", _version("pyClamd")),
    PIPDependency("github", "PyGithub", _version("PyGithub")),
    PIPDependency("git.util", "GitPython", _version("GitPython")),
    PIPDependency("phply", "phply", _version("phply")),
    PIPDependency("chardet", "chardet", _version("chardet")),
    PIPDependency("tblib", "tblib", _version("tblib")),
    PIPDependency("pdfminer", "pdfminer.six", _version("pdfminer.six")),
    PIPDependency("OpenSSL", "pyOpenSSL", _version("pyOpenSSL")),
    PIPDependency("ndg", "ndg-httpsclient", _version("ndg-httpsclient")),
    PIPDependency("pyasn1", "pyasn1", _version("pyasn1")),
    PIPDependency("lxml", "lxml", _version("lxml")),
    PIPDependency("scapy.config", "scapy", _version("scapy")),
    PIPDependency(
        "guess_language", "guess-language-spirit", _version("guess-language-spirit")
    ),
    PIPDependency("cluster", "cluster", _version("cluster")),
    PIPDependency("msgpack", "msgpack", _version("msgpack")),
    PIPDependency("spnego", "pyspnego", _version("pyspnego")),
    PIPDependency("jinja2", "Jinja2", _version("Jinja2")),
    PIPDependency("vulndb", "vulndb", _version("vulndb")),
    PIPDependency("markdown", "Markdown", _version("Markdown")),
    PIPDependency("psutil", "psutil", _version("psutil")),
    PIPDependency("ds_store", "ds-store", _version("ds-store")),
    PIPDependency("termcolor", "termcolor", _version("termcolor")),
    PIPDependency(
        "mitmproxy",
        "mitmproxy",
        _version("mitmproxy"),
        git_src=PINNED_SOURCES["mitmproxy"],
    ),
    PIPDependency("Flask", "Flask", _version("Flask")),
    PIPDependency("yaml", "PyYAML", _version("PyYAML")),
    PIPDependency("tldextract", "tldextract", _version("tldextract")),
    PIPDependency("pebble", "pebble", _version("pebble")),
    PIPDependency("ahocorapy.keywordtree", "ahocorapy", _version("ahocorapy")),
    PIPDependency("multiregex", "multiregex", _version("multiregex")),
    PIPDependency("diff_match_patch", "diff-match-patch", _version("diff-match-patch")),
    PIPDependency("bravado_core", "bravado-core", _version("bravado-core")),
    PIPDependency("lz4", "lz4", _version("lz4")),
    PIPDependency("vulners", "vulners", _version("vulners")),
]

GUI_PIP_EXTRAS = []
if sys.platform != "win32":
    GUI_PIP_EXTRAS.append(PIPDependency("xdot", "xdot", _version("xdot")))

GUI_PIP_PACKAGES = CORE_PIP_PACKAGES[:]
GUI_PIP_PACKAGES.extend(GUI_PIP_EXTRAS)
