"""
vulners.py

Copyright 2018 Vulners.com Team: Kir Ermakov (isox@vulners.com)

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

import collections
import json
import re

import vulners

from w3af.core.controllers.plugins.grep_plugin import GrepPlugin
from w3af.core.data.bloomfilter.scalable_bloom import ScalableBloomFilter
from w3af.core.data.kb.info_set import InfoSet
from w3af.core.data.kb.vuln import Vuln
from w3af.core.data.misc.cvss import cvss_to_severity
from w3af.core.data.misc.lru import SynchronizedLRUDict
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.options.option_types import STRING
from w3af.core.data.options.option_types import URL as URL_OPTION
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.quick_match.multi_re import MultiRE


class vulners_db(GrepPlugin):
    """
    Find software vulnerabilities using Vulners.com API

    Tests from the console mode:

    With API key:

        plugins grep vulners
        plugins grep config vulners_scanner
        set vulners_api_key YOUR_API_KEY_HERE
        back
        target set target VULNERABLE_WEBSITE
        start

    Without API key:

        plugins grep vulners_scanner
        target set target VULNERABLE_WEBSITE
        start

    :author: Vulners.com Team: Kir Ermakov (isox@vulners.com)
    """

    VULNERS_RULES_URL = URL(
        "https://raw.githubusercontent.com/vulnersCom/detect-rules/master/rules.json"
    )
    VULNERS_API_URL = URL("https://vulners.com/")
    BULLETIN_FIELDS = ("title", "description", "cvss")
    CHECK_TYPES = ("software", "cpe")
    VULNERABILITY_CACHE_SIZE = 512

    def __init__(self):
        GrepPlugin.__init__(self)

        # User configured settings
        self._vulners_rules_url = self.VULNERS_RULES_URL
        self._vulners_api_url = self.VULNERS_API_URL
        self._vulners_api_key = ""

        # Vulners shared objects
        self._vulners_api = None
        self.rules_table = None
        self.rules_updated = False

        self._already_visited = ScalableBloomFilter()
        self._vulnerability_cache = SynchronizedLRUDict(self.VULNERABILITY_CACHE_SIZE)
        self._multi_re = None

    def grep(self, request, response):
        """
        Plugin entry point, search for vulnerable software banners in web
        application HTTP responses.

        :param request: The HTTP request object.
        :param response: The HTTP response object
        :return: None

        """
        # Lock and init rules and API wrapper
        with self._plugin_lock:
            if not self.rules_updated:
                # Updating rules
                self.update_vulners_rules()
                self.rules_updated = True

                # Trying to init Vulners API
                self.setup_vulners_api()

        # Check if we have downloaded rules well.
        # If there is no rules - something went wrong, time to exit.
        # If there is no API instance - same story. We cant go further.
        if not self.rules_table or not self._vulners_api:
            return

        # We do not parse non-text output
        if not response.is_text_or_html():
            return

        if response.get_url().get_domain_path() in self._already_visited:
            return

        self._already_visited.add(response.get_url().get_domain_path())

        raw_response = response.dump()

        # Here we will store unique vulnerability map
        vulnerabilities_summary = {}

        for match, _, _, software_list in self._multi_re.query(raw_response):
            detected_version = match.group(1)

            for software_name in software_list:
                matched_rule = self.rules_table[software_name]

                bulletins = self.check_vulners(
                    software_name=matched_rule["alias"],
                    software_version=detected_version,
                    check_type=matched_rule["type"],
                )

                for bulletin in bulletins:
                    vulnerabilities_summary.setdefault(bulletin["id"], bulletin)

        # Now add KB's for found vulnerabilities
        for bulletin in vulnerabilities_summary.values():
            summary = (
                bulletin.get("description")
                or bulletin.get("title")
                or "no description available"
            )

            v = Vuln(
                name=bulletin["id"],
                desc=f"Vulners bulletin {bulletin['id']}: {summary}",
                severity=cvss_to_severity(bulletin.get("cvss", {}).get("score", 0)),
                response_ids=response.id,
                plugin_name=self.get_name(),
            )

            v.set_url(response.get_url())

            v[VulnerableSoftwareInfoSet.ITAG] = bulletin["id"]

            self.kb_append_uniq_group(
                location_a=self,
                location_b="HTML",
                info=v,
                group_klass=VulnerableSoftwareInfoSet,
            )

    def update_vulners_rules(self):
        """
        Get fresh rules from Vulners Github. The rules are regular expressions
        which are used to extract information from the HTTP response.

        Rules can be found at vulners github repository. They were not included
        into the w3af repository because of licensing incompatibilities.

        Paranoid? Check gitlog and regexes.
        """
        # w3af grep plugins shouldn't (by definition) perform HTTP requests
        # But in this case we're breaking that general rule to retrieve the
        # DB at the beginning of the scan. Network errors are returned by the
        # url opener proxy as a 204 response.
        http_response = self._uri_opener.GET(
            self._vulners_rules_url, binary_response=True, respect_size_limit=False
        )

        if http_response.get_code() != 200:
            msg = (
                "Failed to download the Vulners regex rules table, unexpected"
                " HTTP response code %s"
            )
            self._output.error(msg % http_response.get_code())
            return

        json_table = http_response.get_raw_body()
        self.rules_table = json.loads(json_table)

        # Adapt it for MultiRe structure [(regex,alias)] removing regex duplicated
        regex_aliases = collections.defaultdict(list)
        for software_name in self.rules_table:
            regex_aliases[self.rules_table[software_name].get("regex")] += [
                software_name
            ]

        # Now create fast RE filter
        # Using re.IGNORECASE because w3af is modifying headers when making RAW dump.
        # Why so? Raw must be raw!
        self._multi_re = MultiRE(
            ((regex, regex_aliases.get(regex)) for regex in regex_aliases),
            re.IGNORECASE,
        )

    def setup_vulners_api(self):
        try:
            self._vulners_api = vulners.Vulners(
                api_key=self._vulners_api_key or None,
                base_url=self._vulners_api_url.url_string,
            )
        except vulners.VulnersError as e:
            # The Vulners API requires an API key
            msg = 'Failed to initialize Vulners API: "%s"'
            self._output.error(msg % e)

    def check_vulners(self, software_name, software_version, check_type):
        """
        :return: The list of Vulners bulletins which affect the software
        """
        if not software_name or not software_version:
            return []

        if check_type not in self.CHECK_TYPES:
            return []

        cache_key = (software_name, software_version, check_type)
        if cache_key in self._vulnerability_cache:
            return self._vulnerability_cache[cache_key]

        args = (software_name, software_version, check_type)
        self._output.debug("Detected {} version {} (check type: {})".format(*args))

        if check_type == "cpe":
            software = f"{software_name}:{software_version}"
        else:
            software = {"product": software_name, "version": software_version}

        # Ask Vulners about vulnerabilities, the API might be down or rate
        # limit us, so errors are not fatal.
        try:
            results = self._vulners_api.audit.software(
                [software], fields=list(self.BULLETIN_FIELDS)
            )
        except vulners.VulnersError as e:
            msg = 'Failed to make Vulners API request: "%s"'
            self._output.error(msg % e)
            # Don't cache, maybe next time API will answer correctly.
            return []

        vulnerabilities = [
            bulletin
            for result in results
            for bulletin in result.get("vulnerabilities", [])
        ]
        self._vulnerability_cache[cache_key] = vulnerabilities
        return vulnerabilities

    def get_options(self):
        """
        :return: A list of option objects for this plugin.
        """
        ol = OptionList()

        d = (
            "Vulners API key for extended scanning rate limits."
            " Obtain an API key for free at https://vulners.com/"
        )
        o = opt_factory("vulners_api_key", self._vulners_api_key, d, STRING)
        ol.add(o)

        d = "Vulners API base URL"
        o = opt_factory("vulners_api_url", self._vulners_api_url, d, URL_OPTION)
        ol.add(o)

        d = "URL to download the Vulners software detection rules from"
        o = opt_factory("vulners_rules_url", self._vulners_rules_url, d, URL_OPTION)
        ol.add(o)

        return ol

    def set_options(self, options_list):
        """
        This method sets all the options that are configured using the user
        interface generated by the framework using the result of get_options().
        :param options_list: A dictionary with the options for the plugin.
        :return: No value is returned.
        """
        self._vulners_api_key = options_list["vulners_api_key"].get_value()
        self._vulners_api_url = options_list["vulners_api_url"].get_value()
        self._vulners_rules_url = options_list["vulners_rules_url"].get_value()

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        return """
        This plugin extracts software banners and checks vulnerabilities online
        at vulners.com database.
        
        The Vulners API requires an API key, get a free one at
        https://vulners.com/ and configure it using the vulners_api_key
        user-configured parameter. Without it the plugin is disabled.
        """


class VulnerableSoftwareInfoSet(InfoSet):
    ITAG = "vulnerability_id"
    TEMPLATE = (
        "Vulners plugin detected software with known vulnerabilities."
        ' The identified vulnerability is "{{ name }}".\n'
        "\n"
        " The first ten URLs where vulnerable software was detected are:\n"
        ""
        "{% for url in uris[:10] %}"
        " - {{ url }}\n"
        "{% endfor %}"
    )
