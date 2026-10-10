"""
web_diff.py

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

import os

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.fingerprint_404 import is_404
from w3af.core.controllers.exceptions import BaseFrameworkException, RunOnce
from w3af.core.controllers.misc.decorators import runonce
from w3af.core.controllers.plugins.crawl_plugin import CrawlPlugin
from w3af.core.data.misc.encoding import smart_str_ignore
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.options.option_types import BOOL, LIST, STRING
from w3af.core.data.options.option_types import URL as URL_OPTION_TYPE
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest


class web_diff(CrawlPlugin):
    """
    Compare a local directory with a remote URL path.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    def __init__(self):
        CrawlPlugin.__init__(self)

        # Internal variables
        self._not_exist_remote = []
        self._exist_remote = []

        self._not_eq_content = []
        self._eq_content = []

        # Configuration
        self._ban_url = ["asp", "jsp", "php"]
        self._content = True
        self._local_dir = ""
        self._remote_url_path = URL("http://host.tld/")

    @runonce(exc_class=RunOnce)
    def crawl(self, fuzzable_request, debugging_id):
        """
        GET's local files one by one until done.

        :param debugging_id: A unique identifier for this call to discover()
        :param fuzzable_request: A fuzzable_request instance that contains
                                     (among other things) the URL to test.
        """
        if self._local_dir and self._remote_url_path:
            for directory, directory_names, file_names in os.walk(self._local_dir):
                directory_names.sort()
                self._compare_dir(directory, sorted(file_names))

            self._generate_report()
        else:
            msg = (
                "web_diff plugin: You need to configure a local directory"
                " and a remote URL to use in the diff process."
            )
            raise BaseFrameworkException(msg)

    def _generate_report(self):
        """
        Generates a report based on:
            - self._not_exist_remote
            - self._not_eq_content
            - self._exist_remote
            - self._eq_content
        """
        if len(self._exist_remote):
            msg = (
                "The following files exist in the local directory and in the"
                " remote server:"
            )
            om.out.information(msg)
            for file_name in self._exist_remote:
                om.out.information("- " + file_name)

        if len(self._eq_content):
            msg = (
                "The following files exist in the local directory and in the"
                " remote server and their contents match:"
            )
            om.out.information(msg)
            for file_name in self._eq_content:
                om.out.information("- " + file_name)

        if len(self._not_exist_remote):
            msg = (
                "The following files exist in the local directory and do NOT"
                " exist in the remote server:"
            )
            om.out.information(msg)
            for file_name in self._not_exist_remote:
                om.out.information("- " + file_name)

        if len(self._not_eq_content):
            msg = (
                "The following files exist in the local directory and in the"
                " remote server but their contents don't match:"
            )
            om.out.information(msg)
            for file_name in self._not_eq_content:
                om.out.information("- " + file_name)

        exist = len(self._exist_remote)
        total = len(self._exist_remote) + len(self._not_exist_remote)
        file_stats = f"{exist} of {total}"
        om.out.information("Match files: " + file_stats)

        if self._content:
            eq_content = len(self._eq_content)
            total = len(self._eq_content) + len(self._not_eq_content)
            content_stats = f"{eq_content} of {total}"
            om.out.information("Match contents: " + content_stats)

    def _compare_dir(self, directory, file_names):
        """
        Request from the remote server each one of the files that exist in a
        local directory and keep track of which ones exist and match.

        :param directory: The local directory, inside of self._local_dir
        :param file_names: The names of the files inside of the directory
        """
        remote_directory = self._remote_directory_for(directory)

        for file_name in file_names:
            url = remote_directory.url_join(file_name)
            response = self._uri_opener.GET(url, cache=True)

            if is_404(response):
                self._not_exist_remote.append(url)
                continue

            if response.is_text_or_html():
                self.output_queue.put(FuzzableRequest(response.get_url()))

            self._check_content(response, os.path.join(directory, file_name))
            self._exist_remote.append(url)

    def _remote_directory_for(self, directory):
        """
        :param directory: A local directory, inside of self._local_dir
        :return: The URL of the remote directory that matches the local one
        """
        relative_dir = os.path.relpath(directory, self._local_dir)

        if relative_dir == os.curdir:
            return self._remote_url_path

        relative_url_path = "/".join(relative_dir.split(os.sep)) + "/"
        return self._remote_url_path.url_join(relative_url_path)

    def _check_content(self, response, file_path):
        """
        Check if the contents match.
        """
        extension = os.path.splitext(file_path)[1][1:]

        if not self._content or not extension or extension in self._ban_url:
            return

        try:
            with open(file_path, "rb") as local_fh:
                local_content = local_fh.read()
        except OSError:
            om.out.debug(f'Failed to open file: "{file_path}".')
            return

        if local_content == smart_str_ignore(response.get_body()):
            self._eq_content.append(response.get_url())
        else:
            self._not_eq_content.append(response.get_url())

    def get_options(self):
        """
        :return: A list of option objects for this plugin.
        """
        ol = OptionList()

        d = "When comparing, also compare the content of files."
        o = opt_factory("content", self._content, d, BOOL)
        ol.add(o)

        d = "The local directory used in the comparison."
        o = opt_factory("local_dir", self._local_dir, d, STRING)
        ol.add(o)

        d = "The remote directory used in the comparison."
        o = opt_factory("remote_url_path", self._remote_url_path, d, URL_OPTION_TYPE)
        ol.add(o)

        d = "When comparing content of two files, ignore files with these" "extensions."
        o = opt_factory("banned_ext", self._ban_url, d, LIST)
        ol.add(o)

        return ol

    def set_options(self, options_list):
        """
        This method sets all the options that are configured using the user interface
        generated by the framework using the result of get_options().

        :param options_list: A dictionary with the options for the plugin.
        :return: No value is returned.
        """
        url = options_list["remote_url_path"].get_value()
        self._remote_url_path = url.get_domain_path()

        local_dir = options_list["local_dir"].get_value()
        if os.path.isdir(local_dir):
            self._local_dir = local_dir
        else:
            msg = 'Error in user configuration: "%s" is not a directory.'
            raise BaseFrameworkException(msg % local_dir)

        self._content = options_list["content"].get_value()
        self._ban_url = options_list["banned_ext"].get_value()

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        return """
        This plugin tries to do a diff of two directories, a local and a remote
        one. The idea is to mimic the functionality implemented by the linux
        command "diff" when invoked with two directories.

        Four configurable parameter exist:
            - local_dir
            - remote_url_path
            - banned_ext
            - content

        This plugin will read the file list inside "local_dir", and for each file
        it will request the same filename from the "remote_url_path", matches and
        failures are recorded and saved.

        The content of both files is checked only if "content" is set to True
        and the file extension isn't in the "banned_ext" list.

        The "banned_ext" list should be used to ban script extensions like ASP,
        PHP, etc.
        """
