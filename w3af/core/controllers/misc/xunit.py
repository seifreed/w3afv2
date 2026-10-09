"""
xunit.py

Copyright 2011 Andres Riancho

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

from xml.dom.minidom import parseString
from xml.sax import saxutils

import w3af.core.controllers.output_manager as om


class XunitGen:
    """
    Generate an Xunit XML output file for w3af test scripts.
    Tools like Hudson will be able to parse the gen xunit files and display
    useful data to the user.
    """

    outputfile = "w3aftestscripts.xml"

    def __init__(self, outputfile=None):
        if outputfile:
            self.outputfile = outputfile
        self._stats = {"error": 0, "skip": 0, "pass": 0, "fail": 0}
        self.results = []

    def genfile(self):
        """
        Writes the Xunit file.
        """
        self._stats["total"] = (
            self._stats["error"]
            + self._stats["fail"]
            + self._stats["pass"]
            + self._stats["skip"]
        )

        stats = self._stats
        xml_chunks = [
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<testsuite name="w3aftestscripts" tests="{stats["total"]:d}" '
            f'errors="{stats["error"]:d}" failures="{stats["fail"]:d}" '
            f'skip="{stats["skip"]:d}">'
        ]
        xml_chunks.append("".join(self.results))
        xml_chunks.append("</testsuite>")

        with open(self.outputfile, "w") as output:
            output.write(parseString("".join(xml_chunks)).toprettyxml())

        om.out.information(
            f"XML output file was successfuly generated: {self.outputfile}"
        )

    def add_failure(self, test, fail, took):
        """
        :param test: Qualified name for test case.
            Should have next format:
                {packagename}.{path.to.class.in.module}.{testcase}.
            Examples:
                scripts.script-afd.test_afd
                core.controllers.auto_update.tests.test_autoupd.TesVMgr.testXXX
        :param fail: Failure string
        :param took: Time that took the test to run.
        """

        self._stats["fail"] += 1
        faillines = fail.split("\n")
        quoteattr = saxutils.quoteattr
        pkg, _, test_id = test.rpartition(".")

        failure_text = "\n".join(faillines[:-1])
        self.results.append(
            f"<testcase classname={quoteattr(pkg)} name={quoteattr(test_id)} "
            f'time="{int(took)}">'
            f'<failure type={quoteattr(faillines[-1])} message="">'
            f"<![CDATA[{failure_text}]]></failure>"
            "</testcase>"
        )

    def add_error(self, test, err, took, skipped=False):
        """
        :param test: Qualified name for test case.
            Should have next format:
                {packagename}.{path.to.class.in.module}.{testcase}.
            Examples:
                scripts.script-afd.test_afd
                core.controllers.auto_update.tests.test_autoupd.TesVMgr.testXXX
        :param err: Error string
        :param took: Time that took the test to run.
        """
        if skipped:
            self._stats["skip"] += 1
        else:
            self._stats["error"] += 1
        quoteattr = saxutils.quoteattr
        errlinedets = err.split("\n")[-1].split(":", 1)
        pkg, _, test_id = test.rpartition(".")

        self.results.append(
            f"<testcase classname={quoteattr(pkg)} name={quoteattr(test_id)} "
            f'time="{int(took)}">'
            f"<error type={quoteattr(errlinedets[0])} "
            f"message={quoteattr(errlinedets[-1])}><![CDATA[{err}]]>"
            "</error></testcase>"
        )

    def add_success(self, test, took):
        """
        :param test: Qualified name for test case.
            Should have next format:
                {packagename}.{path.to.class.in.module}.{testcase}.
            Examples:
                scripts.script-afd.test_afd
                core.controllers.auto_update.tests.test_autoupd.TesVMgr.testXXX
        :param took: Time that took the test to run.
        """
        self._stats["pass"] += 1
        quoteattr = saxutils.quoteattr
        pkg, _, test_id = test.rpartition(".")
        self.results.append(
            f"<testcase classname={quoteattr(pkg)} name={quoteattr(test_id)} "
            f'time="{int(took)}" />'
        )
