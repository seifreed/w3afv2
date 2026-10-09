"""
retire_standin.py

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

A small stand-in for the retire.js 2.x command line tool, implementing the
subset of the CLI and of the jsrepository.json format that grep.retirejs uses:

    retire --version
    retire -j --outputformat json --outputpath OUT [--jsrepo DB] --jspath PATH

Like retire.js it exits with 13 when vulnerable libraries were found. The
tests write an executable copy of this file whose first lines define BEHAVIOR,
which overrides DEFAULT_BEHAVIOR to simulate broken installations.
"""

import json
import os
import re
import sys
import time

DEFAULT_BEHAVIOR = {
    "version": "2.2.1",
    "version_exit": 0,
    "scan_exit": None,
    "raw_output": None,
    "delete_output": False,
    "sleep": 0,
}

VERSION_REGEX = r"[0-9][0-9.a-z_\-]+"
VULNERABLE_EXIT_CODE = 13


def parse_args(argv):
    return dict(zip(argv[::2], argv[1::2], strict=True))


def version_tuple(version):
    return tuple(int(part) for part in re.findall(r"\d+", version))


def detect(content, repository):
    for component, entry in repository.items():
        for extractor in entry.get("extractors", {}).get("filecontent", []):
            match = re.search(extractor.replace("§§version§§", VERSION_REGEX), content)
            if match:
                yield component, match.group(1), entry.get("vulnerabilities", [])


def scan_file(path, repository):
    with open(path, errors="ignore") as js_file:
        content = js_file.read()

    results = []
    for component, version, vulnerabilities in detect(content, repository):
        affected = [
            vuln
            for vuln in vulnerabilities
            if version_tuple(version) < version_tuple(vuln["below"])
        ]
        if affected:
            results.append(
                {
                    "component": component,
                    "version": version,
                    "detection": "filecontent",
                    "vulnerabilities": affected,
                }
            )
    return results


def scan(args):
    repository = {}
    if "--jsrepo" in args:
        with open(args["--jsrepo"]) as repo_file:
            repository = json.load(repo_file)

    js_path = args["--jspath"]
    paths = [js_path]
    if os.path.isdir(js_path):
        paths = [os.path.join(js_path, name) for name in sorted(os.listdir(js_path))]

    data = []
    for path in paths:
        results = scan_file(path, repository)
        if results:
            data.append({"file": path, "results": results})

    return {"version": BEHAVIOR["version"], "data": data}


def main(argv):
    if argv[1:] == ["--version"]:
        print(BEHAVIOR["version"])
        return BEHAVIOR["version_exit"]

    time.sleep(BEHAVIOR["sleep"])
    args = parse_args(argv[2:])
    report = scan(args)

    output_path = args["--outputpath"]
    with open(output_path, "w") as output:
        output.write(BEHAVIOR["raw_output"] or json.dumps(report))

    if BEHAVIOR["delete_output"]:
        os.remove(output_path)

    if BEHAVIOR["scan_exit"] is not None:
        return BEHAVIOR["scan_exit"]

    return VULNERABLE_EXIT_CODE if report["data"] else 0


BEHAVIOR = {**DEFAULT_BEHAVIOR, **globals().get("BEHAVIOR", {})}

if __name__ == "__main__":
    sys.exit(main(sys.argv))
