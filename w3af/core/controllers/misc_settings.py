"""
misc_settings.py

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

from vulndb import DBVuln

from w3af.core.configurable import Configurable
from w3af.core.controllers.misc.get_local_ip import get_local_ip
from w3af.core.controllers.misc.get_net_iface import get_net_iface
from w3af.core.data.db.variant_db import (
    MAX_EQUAL_FORM_VARIANTS,
    PARAMS_MAX_VARIANTS,
    PATH_MAX_VARIANTS,
)
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.options.option_types import (
    BOOL,
    COMBO,
    FORM_ID_LIST,
    INT,
    LIST,
    STRING,
    URL_LIST,
)
from w3af.core.data.parsers.utils.form_constants import EXCLUDE, INCLUDE
from w3af.core.data.parsers.utils.form_id_matcher_list import FormIDMatcherList


class MiscSettings(Configurable):
    """
    A class that acts as an interface for the user interfaces, so they can
    configure w3af settings using get_options and SetOptions.
    """

    def __init__(self, configuration):
        """
        Set the defaults and save them to the config dict.
        """
        self._configuration = configuration
        if not self.is_configured():
            # It's the first time I'm run
            self.set_default_values()

    def is_configured(self):
        return self._configuration.get("fuzz_cookies") is not None

    def set_default_values(self):
        """
        Load all the default settings
        :return: None
        """
        self._configuration.save("fuzz_cookies", False)
        self._configuration.save("fuzz_form_files", True)
        self._configuration.save("fuzzed_files_extension", "gif")
        self._configuration.save("fuzz_url_filenames", False)
        self._configuration.save("fuzz_url_parts", False)
        self._configuration.save("fuzzable_headers", [])

        self._configuration.save("form_fuzzing_mode", "tmb")

        self._configuration.save("path_max_variants", PATH_MAX_VARIANTS)
        self._configuration.save("params_max_variants", PARAMS_MAX_VARIANTS)
        self._configuration.save("max_equal_form_variants", MAX_EQUAL_FORM_VARIANTS)

        self._configuration.save("max_discovery_time", 120)
        self._configuration.save("max_scan_time", 240)

        self._configuration.save("msf_location", "/opt/metasploit3/bin/")

        #
        # The network interface configuration (for advanced exploits)
        #
        ifname = get_net_iface()
        self._configuration.save("interface", ifname)

        #
        # This doesn't send any packets, and gives you a nice default
        # setting. In most cases, it is the "public" IP address, which will
        # work perfectly in all plugins that need a reverse connection
        # (rfi_proxy)
        #
        local_address = get_local_ip()
        if not local_address:
            local_address = "127.0.0.1"  # do'h!

        self._configuration.save("local_ip_address", local_address)
        self._configuration.save("stop_on_first_exception", False)

        # Blacklists
        self._configuration.save("blacklist_http_request", [])
        self._configuration.save("blacklist_audit", [])

        # Form exclusion via IDs
        self._configuration.save("form_id_list", FormIDMatcherList("[]"))
        self._configuration.save("form_id_action", EXCLUDE)

        # Language to use when reading from vulndb
        self._configuration.save("vulndb_language", DBVuln.DEFAULT_LANG)

    def get_options(self):
        """
        :return: A list of option objects for this plugin.
        """
        ol = OptionList()

        #
        # Fuzzer parameters
        #
        d = "Indicates if w3af plugins will use cookies as a fuzzable parameter"
        opt = opt_factory(
            "fuzz_cookies",
            self._configuration.get("fuzz_cookies"),
            d,
            BOOL,
            tabid="Fuzzer parameters",
        )
        ol.add(opt)

        d = (
            "Indicates if w3af plugins will send payloads in the content of"
            " multipart/post form files."
        )
        h = (
            "If enabled, and multipart/post forms with files are found, w3af"
            "will fill those file inputs with pseudo-files containing the"
            "payloads required to identify vulnerabilities."
        )
        opt = opt_factory(
            "fuzz_form_files",
            self._configuration.get("fuzz_form_files"),
            d,
            BOOL,
            tabid="Fuzzer parameters",
            help=h,
        )
        ol.add(opt)

        d = (
            "Indicates if w3af plugins will send fuzzed file names in order to"
            " find vulnerabilities"
        )
        h = (
            "For example, if the discovered URL is http://test/filename.php,"
            " and fuzz_url_filenames is enabled, w3af will request among"
            " other things: http://test/file'a'a'name.php in order to"
            " find SQL injections. This type of vulns are getting more "
            " common every day!"
        )
        opt = opt_factory(
            "fuzz_url_filenames",
            self._configuration.get("fuzz_url_filenames"),
            d,
            BOOL,
            help=h,
            tabid="Fuzzer parameters",
        )
        ol.add(opt)

        desc = (
            "Indicates if w3af plugins will send fuzzed URL parts in order"
            " to find vulnerabilities"
        )
        h = (
            "For example, if the discovered URL is http://test/foo/bar/123,"
            " and fuzz_url_parts is enabled, w3af will request among other "
            " things: http://test/bar/<script>alert(document.cookie)</script>"
            " in order to find XSS."
        )
        opt = opt_factory(
            "fuzz_url_parts",
            self._configuration.get("fuzz_url_parts"),
            desc,
            BOOL,
            help=h,
            tabid="Fuzzer parameters",
        )
        ol.add(opt)

        desc = "Indicates the extension to use when fuzzing file content"
        opt = opt_factory(
            "fuzzed_files_extension",
            self._configuration.get("fuzzed_files_extension"),
            desc,
            STRING,
            tabid="Fuzzer parameters",
        )
        ol.add(opt)

        desc = "A list with all fuzzable header names"
        opt = opt_factory(
            "fuzzable_headers",
            self._configuration.get("fuzzable_headers"),
            desc,
            LIST,
            tabid="Fuzzer parameters",
        )
        ol.add(opt)

        d = (
            "Indicates what HTML form combo values w3af plugins will use:"
            " all, tb, tmb, t, b"
        )
        h = (
            "Indicates what HTML form combo values, e.g. select options values,"
            " w3af plugins will use: all (All values), tb (only top and bottom"
            " values), tmb (top, middle and bottom values), t (top values), b"
            " (bottom values)."
        )
        options = ["tmb", "all", "tb", "t", "b"]
        opt = opt_factory(
            "form_fuzzing_mode", options, d, COMBO, help=h, tabid="Fuzzer parameters"
        )
        ol.add(opt)

        #
        # Core parameters
        #
        desc = "Stop scan after first unhandled exception"
        h = (
            "This feature is only useful for developers that want their scan"
            " to stop on the first exception that is raised by a plugin."
            " Users should leave this as False in order to get better"
            " exception handling from w3af's core."
        )
        opt = opt_factory(
            "stop_on_first_exception",
            self._configuration.get("stop_on_first_exception"),
            desc,
            BOOL,
            help=h,
            tabid="Core settings",
        )
        ol.add(opt)

        desc = "Maximum crawl time (minutes)"
        h = (
            "Many users tend to enable numerous plugins without actually"
            " knowing what they are and the potential time they will take"
            " to run. By using this parameter, users will be able to set"
            " the maximum amount of time the crawl phase will run."
        )
        opt = opt_factory(
            "max_discovery_time",
            self._configuration.get("max_discovery_time"),
            desc,
            INT,
            help=h,
            tabid="Core settings",
        )
        ol.add(opt)

        desc = "Maximum scan time (minutes)"
        h = (
            "Sets the maximum number of minutes for the scan to run. Use"
            " zero to remove the limit."
        )
        opt = opt_factory(
            "max_scan_time",
            self._configuration.get("max_scan_time"),
            desc,
            INT,
            help=h,
            tabid="Core settings",
        )
        ol.add(opt)

        desc = "Limit requests for each URL sub-path"
        h = (
            "Limit how many requests are performed for each URL sub-path"
            " during crawling. For example, if the application links to"
            " three products: /product/1 /product/2 and /product/3, and"
            " this variable is set to two, only the first two URLs:"
            " /product/1 and /product/2 will be crawled."
        )
        opt = opt_factory(
            "path_max_variants",
            self._configuration.get("path_max_variants"),
            desc,
            INT,
            help=h,
            tabid="Core settings",
        )
        ol.add(opt)

        desc = "Limit requests for each URL and parameter set"
        h = (
            "Limit how many requests are performed for each URL and parameter"
            " set. For example, if the application links to three products:"
            " /product?id=1 , /product?id=2 and /product?id=3, and this"
            " variable is set to two, only the first two URLs:"
            " /product?id=1 and /product?id=2 will crawled."
        )
        opt = opt_factory(
            "params_max_variants",
            self._configuration.get("params_max_variants"),
            desc,
            INT,
            help=h,
            tabid="Core settings",
        )
        ol.add(opt)

        desc = "Limit requests for similar forms"
        h = (
            "Limit the number of HTTP requests to be sent to similar forms"
            " during crawling. For example, if the application has multiple"
            " HTML forms with the same parameters and different URLs set in"
            " actions then only the configured number of forms are crawled."
        )
        opt = opt_factory(
            "max_equal_form_variants",
            self._configuration.get("max_equal_form_variants"),
            desc,
            INT,
            help=h,
            tabid="Core settings",
        )
        ol.add(opt)

        #
        # Network parameters
        #
        desc = (
            "Local interface name to use when sniffing, doing reverse"
            " connections, etc."
        )
        opt = opt_factory(
            "interface",
            self._configuration.get("interface"),
            desc,
            STRING,
            tabid="Network settings",
        )
        ol.add(opt)

        desc = "Local IP address to use when doing reverse connections"
        opt = opt_factory(
            "local_ip_address",
            self._configuration.get("local_ip_address"),
            desc,
            STRING,
            tabid="Network settings",
        )
        ol.add(opt)

        #
        # URL and form exclusions
        #
        desc = "List of URLs that must be completely ignored by the scan engine"
        h = (
            "A comma separated list of URLs which must never receive an"
            " HTTP requests from w3af"
        )
        opt = opt_factory(
            "blacklist_http_request",
            self._configuration.get("blacklist_http_request"),
            desc,
            URL_LIST,
            help=h,
            tabid="Exclusions",
        )
        ol.add(opt)

        desc = "List of URLs to ignore during the HTTP fuzzing phase"
        h = (
            "A comma separated list of URLs which can receive traffic from"
            " crawl plugins but must never receive HTTP fuzzing from audit"
            " plugins"
        )
        opt = opt_factory(
            "blacklist_audit",
            self._configuration.get("blacklist_audit"),
            desc,
            URL_LIST,
            help=h,
            tabid="Exclusions",
        )
        ol.add(opt)

        desc = "Filter forms to scan using form IDs"
        h = (
            "Form IDs allow the user to specify which forms will be either"
            " included of excluded in the scan. The form IDs identified by"
            " w3af will be written to the log (when verbose is set to true)"
            " and can be used to define this setting for new scans.\n\n"
            'Find more about form IDs in the "Advanced use cases" section'
            "of the w3af documentation."
        )
        opt = opt_factory(
            "form_id_list",
            self._configuration.get("form_id_list"),
            desc,
            FORM_ID_LIST,
            help=h,
            tabid="Exclusions",
        )
        ol.add(opt)

        desc = "Define the form_id_list filter behaviour"
        h = (
            'Change this setting to "include" if only a very specific set of'
            " forms needs to be scanned. If forms matching the form_id_list"
            ' parameters need to be excluded then set this value to "exclude".'
        )

        form_id_actions = [EXCLUDE, INCLUDE]
        tmp_list = form_id_actions[:]
        tmp_list.remove(self._configuration.get("form_id_action"))
        tmp_list.insert(0, self._configuration.get("form_id_action"))

        opt = opt_factory(
            "form_id_action", tmp_list, desc, COMBO, help=h, tabid="Exclusions"
        )
        ol.add(opt)

        #
        # Metasploit
        #
        desc = (
            "Full path of Metasploit framework binary directory ({} in "
            "most linux installs)".format(self._configuration.get("msf_location"))
        )
        opt = opt_factory(
            "msf_location",
            self._configuration.get("msf_location"),
            desc,
            STRING,
            tabid="Metasploit",
        )
        ol.add(opt)

        #
        # Language options
        #
        d = "Set the language to use when reading from the vulnerability database"
        h = (
            "The vulnerability database stores descriptions, fix guidance, tags,"
            " references and much more about each vulnerability the scanner can"
            " identify. The database supports translations, so this information"
            " can be in many languages. Use this setting to choose the language"
            " in which the information will be displayed and stored in reports."
        )
        options = DBVuln.get_all_languages()
        opt = opt_factory(
            "vulndb_language", options, d, COMBO, help=h, tabid="Language"
        )
        ol.add(opt)

        return ol

    def get_desc(self):
        return (
            "This section is used to configure misc settings that affect"
            " the core and all plugins."
        )

    def set_options(self, options_list):
        """
        This method sets all the options that are configured using the user
        interface generated by the framework using the result of get_options().

        :param options_list: A dictionary with the options for the plugin.
        :return: No value is returned.
        """
        to_save = (
            "fuzz_cookies",
            "fuzz_form_files",
            "fuzz_url_filenames",
            "fuzz_url_parts",
            "fuzzed_files_extension",
            "form_fuzzing_mode",
            "max_discovery_time",
            "max_scan_time",
            "fuzzable_headers",
            "interface",
            "local_ip_address",
            "msf_location",
            "stop_on_first_exception",
            "blacklist_http_request",
            "blacklist_audit",
            "form_id_action",
            "form_id_list",
            "path_max_variants",
            "params_max_variants",
            "max_equal_form_variants",
            "vulndb_language",
        )

        for name in to_save:
            self._configuration.save(name, options_list[name].get_value())
