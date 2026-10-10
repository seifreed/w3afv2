# -*- coding: UTF-8 -*-
"""
test_complex_html_form.py

Copyright 2017 Andres Riancho

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
import unittest
from typing import ClassVar

from w3af import ROOT_PATH
from w3af.core.data.parsers.doc.tests.test_html import RaiseHTMLParser
from w3af.core.data.parsers.doc.tests.test_sgml import build_http_response
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.utils.form_constants import MODE_TMB


class TestComplexHTMLForm(unittest.TestCase):
    url = URL("http://w3af.com")
    COMPLEX_FORM = os.path.join(
        ROOT_PATH,
        "core",
        "data",
        "parsers",
        "doc",
        "tests",
        "data",
        "complex-form.html",
    )

    EXPECTED_PARAMS: ClassVar[list[str]] = [
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__PREVIOUSPAGE",
        "__EVENTVALIDATION",
        "ctl00$ucLogin$txtAnvnamn",
        "ctl00$ucLogin$txtLosen",
        "ctl00$ucLogin$btnLoggain",
        "ctl00$cphHuvud$btnSok1",
        "ctl00$cphHuvud$btnSokObj1",
        "ctl00$cphHuvud$ListaGrundschema",
        "ctl00$cphHuvud$bnMarkeraAlla",
        "ctl00$cphHuvud$bnAvmarkeraAlla",
        "ctl00$cphHuvud$ListaObjurval",
        "ctl00$cphHuvud$grundschemanamn",
        "ctl00$cphHuvud$soktyp",
        "ctl00$cphHuvud$visalediga",
        "ctl00$cphHuvud$passstart",
        "ctl00$cphHuvud$passslut",
        "ctl00$cphHuvud$passlangd",
        "ctl00$cphHuvud$visabokade",
        "ctl00$cphHuvud$sortera",
        "ctl00$cphHuvud$hdnDatediff",
        "ctl00$cphHuvud$txtFdat",
        "ctl00$cphHuvud$txtTdat",
        "ctl00$cphHuvud$hdnMaxdgr",
        "ctl00$cphHuvud$btnSok2",
        "ctl00$cphHuvud$btnSokObj2",
        "ctl00$cphHuvud$ibnSv",
        "ctl00$cphHuvud$ibnNo",
        "ctl00$cphHuvud$ibnEn",
        "ctl00$cphHuvud$ibnIs",
    ]

    def test_complex_form_parse_and_variants(self):
        """
        Reported by one of our partners. The issue seems to be that there are
        too many variants being generated.
        """
        with open(self.COMPLEX_FORM, "rb") as form_file:
            body = form_file.read()
        resp = build_http_response(self.url, body)
        p = RaiseHTMLParser(resp)
        p.parse()

        form_params = p.forms[0]
        self.assertEqual(
            len([fv for fv in form_params.get_variants(MODE_TMB)]),
            form_params.TOP_VARIANTS + 1,
        )

        self.assertEqual(len(list(form_params.meta.keys())), 31)
        self.assertEqual(list(form_params.meta), self.EXPECTED_PARAMS)
