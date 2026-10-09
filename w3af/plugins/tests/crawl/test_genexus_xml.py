"""
test_genexus_xml.py

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

from typing import ClassVar

from w3af.plugins.crawl.genexus_xml import genexus_xml
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

RUN_PLUGINS = {"crawl": (PluginConfig("genexus_xml"),)}


class TestGenexusXML(PluginTest):

    target_url = "http://httpretty-mock/"

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"crawl": (PluginConfig("genexus_xml"),)},
        }
    }

    EXECUTE_XML = """<?xml-stylesheet type='text/xsl' href='prgs.xsl'?>
                     <Objects>
                        <Charset>iso-8859-1</Charset>
                        <Path>file:///C:/GeneXus/</Path>
                        <Object>
                            <ObjCls>13</ObjCls>
                            <ObjName>hidden</ObjName>
                            <ObjDesc>Small description</ObjDesc>
                            <ObjLink>hidden.aspx</ObjLink>
                        </Object>
                        <Object>
                            <ObjCls>13</ObjCls>
                            <ObjName>HMaster</ObjName>
                            <ObjDesc>Master description</ObjDesc>
                            <ObjLink>hmaster.aspx</ObjLink>
                        </Object>
                    </Objects>"""

    DEVELOPER_MENU_XML = """
    <?xml version="1.0" encoding="iso-8859-1"?>
    <Objects>
       <Charset>iso-8859-1</Charset>
       <Path>file:///C:/GeneXus/</Path>
       <Object>
          <ObjCls>0</ObjCls>
          <ObjName>Faith</ObjName>
          <ObjDesc>Load description</ObjDesc>
          <ObjLink>foobar.aspx</ObjLink>
       </Object>
    </Objects>"""

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://httpretty-mock/execute.xml",
            EXECUTE_XML,
            content_type="application/xml",
        ),
        MockResponse(
            "http://httpretty-mock/DeveloperMenu.xml",
            DEVELOPER_MENU_XML,
            content_type="application/xml",
        ),
        MockResponse("http://httpretty-mock/hidden.aspx", "Exists"),
        MockResponse("http://httpretty-mock/foobar.aspx", "Exists"),
    ]

    def test_genexus_xml(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        dev_infos = self.kb.get("genexus_xml", "DeveloperMenu.xml")
        self.assertEqual(len(dev_infos), 1)
        dev_info = dev_infos[0]
        self.assertEqual(
            dev_info.get_url().url_string, "http://httpretty-mock/DeveloperMenu.xml"
        )

        exec_infos = self.kb.get("genexus_xml", "execute.xml")
        self.assertEqual(len(exec_infos), 1)
        exec_info = exec_infos[0]
        self.assertEqual(
            exec_info.get_url().url_string, "http://httpretty-mock/execute.xml"
        )

        urls = self.kb.get_all_known_urls()

        EXPECTED_URLS = {
            "http://httpretty-mock/hidden.aspx",
            "http://httpretty-mock/foobar.aspx",
            "http://httpretty-mock/execute.xml",
            "http://httpretty-mock/DeveloperMenu.xml",
            "http://httpretty-mock/",
        }
        urls = {u.url_string for u in urls}

        self.assertEqual(EXPECTED_URLS, urls)


class TestGenexusXMLInvalidEntries(PluginTest):

    target_url = "http://mock/"

    DEVELOPER_MENU_XML = (
        "<Objects>"
        "<Object><ObjLink>//[</ObjLink></Object>"
        "<Object><ObjLink></ObjLink></Object>"
        "<Object><ObjLink><b>nested</b></ObjLink></Object>"
        "<Object><ObjLink>valid.aspx</ObjLink></Object>"
        "</Objects>"
    )

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/", "Index"),
        MockResponse(
            "http://mock/execute.xml", "<ObjLink>gone.aspx</ObjLink>", status=404
        ),
        MockResponse("http://mock/DeveloperMenu.xml", DEVELOPER_MENU_XML),
        MockResponse("http://mock/valid.aspx", "Exists"),
    ]

    def test_only_valid_links_are_followed(self):
        self._scan(self.target_url, RUN_PLUGINS)

        self.assertEqual(self.kb.get("genexus_xml", "execute.xml"), [])
        self.assertEqual(len(self.kb.get("genexus_xml", "DeveloperMenu.xml")), 1)

        urls = {u.url_string for u in self.kb.get_all_known_urls()}
        self.assertEqual(
            urls,
            {
                "http://mock/",
                "http://mock/DeveloperMenu.xml",
                "http://mock/valid.aspx",
            },
        )


class TestGenexusXMLMalformed(PluginTest):

    target_url = "http://mock/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/", "Index"),
        MockResponse(
            "http://mock/DeveloperMenu.xml", "<Objects><ObjLink>a.aspx</ObjLink>"
        ),
    ]

    def test_malformed_xml_is_reported_without_links(self):
        self._scan(self.target_url, RUN_PLUGINS)

        self.assertEqual(self.kb.get("genexus_xml", "execute.xml"), [])
        self.assertEqual(len(self.kb.get("genexus_xml", "DeveloperMenu.xml")), 1)

        requested_paths = {request.path for request in self.received_requests}
        self.assertNotIn("/a.aspx", requested_paths)

    def test_long_description(self):
        self.assertIn("execute.xml", genexus_xml().get_long_desc())
