"""
ds_store.py

Copyright 2013 Tomas Velazquez

This file is part of w3af, w3af.sourceforge.net .

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

from io import BytesIO

from ds_store import DSStore
from ds_store.buddy import BuddyError

from w3af.core.controllers.plugins.crawl_plugin import CrawlPlugin
from w3af.core.data.constants import severity
from w3af.core.data.db.disk_set import DiskSet
from w3af.core.data.kb.vuln import Vuln


class dot_ds_store(CrawlPlugin):
    """
    Search .DS_Store file and checks for files containing.

    :author: Tomas Velazquez ( tomas.velazquezz@gmail.com )
    :author: Andres Riancho ( andres.riancho@gmail.com )

    :credits: This code was based in cpan Mac::Finder::DSStore by Wim Lewis ( wiml@hhhh.org )
    """

    DS_STORE = ".DS_Store"

    def __init__(self):
        CrawlPlugin.__init__(self)

        # Internal variables
        self._analyzed_dirs = DiskSet()

    def crawl(self, fuzzable_request, debugging_id):
        """
        For every directory, fetch a list of files and analyze the response.

        :param debugging_id: A unique identifier for this call to discover()
        :parameter fuzzable_request: A fuzzable_request instance that contains
                                    (among other things) the URL to test.
        """
        directories_to_check = []

        for domain_path in fuzzable_request.get_url().get_directories():
            if domain_path not in self._analyzed_dirs:
                self._analyzed_dirs.add(domain_path)
                directories_to_check.append(domain_path)

        # Send the requests using threads
        self.worker_pool.map(self._check_and_analyze, directories_to_check)

    def _check_and_analyze(self, domain_path):
        """
        Check if a .DS_Store filename exists in the domain_path.

        :return: None, everything is saved to the self.out_queue.
        """
        url = domain_path.url_join(self.DS_STORE)
        response = self.http_get_and_parse(url, binary_response=True)

        # Check if it's a .DS_Store file
        if self._is_404(response):
            return

        try:
            store = DsStore(response.get_raw_body())
            entries = store.get_file_entries()
        except (
            BuddyError,
            OSError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
        ) as e:
            self._output.debug(f'Unexpected error while parsing DS_Store file: "{e}"')
            return

        parsed_url_list = []

        for filename in entries:
            parsed_url_list.append(domain_path.url_join(filename))

        self.worker_pool.map(self.http_get_and_parse, parsed_url_list)

        desc = (
            "A .DS_Store file was found at: %s. The contents of this file"
            " disclose filenames"
        )
        desc %= response.get_url()

        v = Vuln(
            ".DS_Store file found", desc, severity.LOW, response.id, self.get_name()
        )
        v.set_url(response.get_url())

        self._get_knowledge_base().append(self, "dot_ds_store", v)
        self._output.vulnerability(v.get_desc(), severity=v.get_severity())

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        return """
        This plugin searches for the .DS_Store file in all the directories and
        subdirectories that are sent as input. If the file is found extract new
        URLs from its content.
        
        The .DS_Store file holds information about the list of files in the 
        current directory. These files are created by the Mac OS X Finder in every
        directory that it accesses.
        
        For example, if the plugin input is:
            - http://host.tld/w3af/index.php

        The plugin will perform these requests:
            - http://host.tld/w3af/.DS_Store
            - http://host.tld/.DS_Store
        """


class DsStore:

    def __init__(self, data):
        self._store = None
        self.init(data)

    def init(self, data):
        """
        Open a .DS_Store file
        """
        self._store = DSStore.open(BytesIO(data), "r")

    def get_file_entries(self):
        entries = set()

        for entry in self._store:
            filename = entry.filename
            if filename in (".", ".."):
                continue

            entries.add(filename)

        return entries
