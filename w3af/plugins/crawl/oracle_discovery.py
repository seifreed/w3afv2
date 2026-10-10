"""
oracle_discovery.py

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

import re
from typing import ClassVar

from w3af.core.controllers.misc.decorators import runonce
from w3af.core.controllers.plugins.crawl_plugin import CrawlPlugin
from w3af.core.data.kb.info import Info
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.exceptions import RunOnce


class oracle_discovery(CrawlPlugin):
    """
    Find Oracle applications on the remote web server.
    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    ORACLE_URL = ("/portal/page", "/reports/rwservlet/showenv")

    ORACLE_RE_PATTERNS = (
        # Example string:
        # <html><head><title>PPE is working</title></head><body>
        # PPE version 1.3.4 is working.</body></html>
        (
            "<html><head><title>PPE is working</title></head>"
            "<body>(PPE) version (.*?) is working.</body></html>"
        ),
        # Example strings:
        # Reports Servlet Omgevingsvariabelen 9.0.4.2.0
        # Reports Servlet Variables de Entorno 9.0.4.0.33
        r"(Reports Servlet) [\w ]* ([\d\.]+)",
    )

    ORACLE_RE: ClassVar = [re.compile(regex, re.DOTALL) for regex in ORACLE_RE_PATTERNS]

    @runonce(exc_class=RunOnce)
    def crawl(self, fuzzable_request, debugging_id):
        """
        GET some files and parse them.

        :param debugging_id: A unique identifier for this call to discover()
        :param fuzzable_request: A fuzzable_request instance that contains
                                    (among other things) the URL to test.
        """
        self.worker_pool.map(self.send_and_check, self.url_generator(fuzzable_request))

    def url_generator(self, fuzzable_request):
        base_url = fuzzable_request.get_url().base_url()

        for url in self.ORACLE_URL:
            yield base_url.url_join(url)

    def send_and_check(self, url):

        response = self.http_get_and_parse(url)

        for regex in self.ORACLE_RE:
            mo = regex.search(response.get_body())

            if mo:
                desc = '"%s" version "%s" was detected at "%s".'
                desc %= (mo.group(1).title(), mo.group(2).title(), response.get_url())

                i = Info(
                    "Oracle Application Server", desc, response.id, self.get_name()
                )
                i.set_url(response.get_url())

                self._get_knowledge_base().append(self, "oracle_discovery", i)
                self._output.information(i.get_desc())

                fr = FuzzableRequest.from_http_response(
                    response, configuration=self.get_configuration()
                )
                self.output_queue.put(fr)

                break

        else:
            msg = (
                'oracle_discovery found the URL: "%s" but failed to'
                " parse it as an Oracle page. The first 50 bytes of"
                ' the response body is: "%s".'
            )
            body_start = response.get_body()[:50]
            self._output.debug(msg % (response.get_url(), body_start))

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        return """
        This plugin retrieves Oracle Application Server URLs and extracts
        information available on them.
        """
