"""
wavsep_xss_site.py

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

import re
from dataclasses import dataclass

from w3af.plugins.tests.audit.vulnerable_responses import html_page, request_params
from w3af.plugins.tests.audit.vulnerable_xss import EchoPage
from w3af.plugins.tests.helper import MockResponse

VIEWSTATE = "dDwtMTQ2NDQ5NDE5NDs7Pg=="
USER_INPUT = ("userinput",)


@dataclass(frozen=True)
class XssCase:
    """
    A reflected XSS page: the HTML context where the input is written.
    """

    file_name: str
    template: str
    params: tuple[str, ...] = USER_INPUT
    status: int = 200
    required: tuple[tuple[str, str], ...] = ()


CASES = (
    XssCase("Case01-Tag2HtmlPageScope.jsp", "<p>$userinput</p>"),
    XssCase("Case02-Tag2TagScope.jsp", '<input type="text" $userinput>'),
    XssCase("Case03-Tag2TagStructure.jsp", "<a href=$userinput>link</a>"),
    XssCase("Case04-Tag2HtmlComment.jsp", "<!-- $userinput -->"),
    XssCase(
        "Case05-Tag2Frameset.jsp",
        '<frameset rows="100%"><frame src="a.html"/>$userinput</frameset>',
    ),
    XssCase("Case06-Event2TagScope.jsp", '<img src="a.png" alt="a" $userinput>'),
    XssCase(
        "Case07-Event2DoubleQuotePropertyScope.jsp",
        '<input type="text" value="$userinput">',
    ),
    XssCase(
        "Case08-Event2SingleQuotePropertyScope.jsp",
        "<input type=\"text\" value='$userinput'>",
    ),
    XssCase("Case09-SrcProperty2TagStructure.jsp", '<img src="$userinput">'),
    XssCase(
        "Case10-Js2DoubleQuoteJsEventScope.jsp",
        '<input type="button" onclick=\'var a="$userinput";\'>',
    ),
    XssCase(
        "Case11-Js2SingleQuoteJsEventScope.jsp",
        '<input type="button" onclick="var a=\'$userinput\';">',
    ),
    XssCase(
        "Case12-Js2JsEventScope.jsp",
        '<input type="button" onclick="var a=$userinput;">',
    ),
    XssCase(
        "Case13-Vbs2DoubleQuoteVbsEventScope.jsp",
        '<input type="button" language="vbscript" onclick=\'a = "$userinput"\'>',
    ),
    XssCase(
        "Case14-Vbs2SingleQuoteVbsEventScope.jsp",
        '<input type="button" language="vbscript" onclick="a = \'$userinput\'">',
    ),
    XssCase(
        "Case15-Vbs2VbsEventScope.jsp",
        '<input type="button" language="vbscript" onclick="a = $userinput">',
    ),
    XssCase("Case16-Js2ScriptSupportingProperty.jsp", '<a href="$userinput">x</a>'),
    XssCase(
        "Case17-Js2PropertyJsScopeDoubleQuoteDelimiter.jsp",
        "<a href='javascript:alert(\"$userinput\")'>x</a>",
    ),
    XssCase(
        "Case18-Js2PropertyJsScopeSingleQuoteDelimiter.jsp",
        "<a href=\"javascript:alert('$userinput')\">x</a>",
    ),
    XssCase(
        "Case19-Js2PropertyJsScope.jsp",
        '<a href="javascript:alert($userinput)">x</a>',
    ),
    XssCase(
        "Case20-Vbs2PropertyVbsScopeDoubleQuoteDelimiter.jsp",
        "<a href='vbscript:msgbox(\"$userinput\")'>x</a>",
    ),
    XssCase(
        "Case21-Vbs2PropertyVbsScope.jsp",
        '<a href="vbscript:msgbox($userinput)">x</a>',
    ),
    XssCase(
        "Case22-Js2ScriptTagDoubleQuoteDelimiter.jsp",
        '<script>var a="$userinput";</script>',
    ),
    XssCase(
        "Case23-Js2ScriptTagSingleQuoteDelimiter.jsp",
        "<script>var a='$userinput';</script>",
    ),
    XssCase("Case24-Js2ScriptTag.jsp", "<script>var a=$userinput;</script>"),
    XssCase(
        "Case25-Vbs2ScriptTagDoubleQuoteDelimiter.jsp",
        '<script language="vbscript">a = "$userinput"</script>',
    ),
    XssCase(
        "Case26-Vbs2ScriptTag.jsp",
        '<script language="vbscript">a = $userinput</script>',
    ),
    XssCase(
        "Case27-Js2ScriptTagOLCommentScope.jsp",
        "<script>// $userinput\n</script>",
    ),
    XssCase(
        "Case28-Js2ScriptTagMLCommentScope.jsp",
        "<script>/* $userinput */</script>",
    ),
    XssCase(
        "Case29-Vbs2ScriptTagOLCommentScope.jsp",
        '<script language="vbscript">\' $userinput\n</script>',
    ),
    XssCase(
        "Case30-Tag2HtmlPageScopeMultipleVulnerabilities.jsp",
        "<p>$userinput</p><p>$userinput2</p>",
        params=("userinput", "userinput2"),
    ),
    XssCase(
        "Case31-Tag2HtmlPageScopeDuringException.jsp",
        "<p>Exception: $userinput</p>",
        status=500,
    ),
    XssCase(
        "Case32-Tag2HtmlPageScopeValidViewstateRequired.jsp",
        "<p>$userinput</p>",
        params=("userinput", "__VIEWSTATE"),
        required=(("__VIEWSTATE", VIEWSTATE),),
    ),
)


def case_defaults(case):
    return {
        param: VIEWSTATE if param == "__VIEWSTATE" else "textvalue"
        for param in case.params
    }


def expected_vulns(case):
    """
    :return: The (page, vulnerable parameter, all the parameters) tuples
    """
    vulnerable = [p for p in case.params if p != "__VIEWSTATE"]
    return [(case.file_name, param, list(case.params)) for param in vulnerable]


class ViewStateChecker:
    """
    Writes the page only when the request contains the required parameters
    with the expected values, as ASP.NET does with its view state.
    """

    def __init__(self, page, required):
        self.page = page
        self.required = dict(required)

    def __call__(self, mock_response, request, uri, response_headers):
        params = request_params(request)
        if all(params.get(name) == value for name, value in self.required.items()):
            return self.page(mock_response, request, uri, response_headers)
        return html_page(response_headers, "Invalid view state")


def case_handler(case):
    page = EchoPage(case.template, status=case.status)
    if case.required:
        return ViewStateChecker(page, case.required)
    return page


def index_body():
    links = []
    for case in CASES:
        query = "&".join(f"{k}={v}" for k, v in case_defaults(case).items())
        links.append(f'<a href="{case.file_name}?{query}">{case.file_name}</a><br/>')
    return "<html><body>" + "".join(links) + "</body></html>"


def wavsep_xss_responses(base_url):
    responses = [MockResponse(base_url, index_body())]

    for case in CASES:
        url = re.compile(re.escape(base_url + case.file_name) + r"(\?.*)?$")
        responses.append(MockResponse(url, case_handler(case)))

    return responses
