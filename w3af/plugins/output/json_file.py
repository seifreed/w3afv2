"""
json_file.py

Copyright 2012 Andres Riancho

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

import base64
import json
import os
import time

from w3af.core.controllers.misc import get_w3af_version
from w3af.core.controllers.plugins.output_plugin import OutputPlugin
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.options.option_types import OUTPUT_FILE

TIME_FORMAT = "%a %b %d %H:%M:%S %Y"


class json_file(OutputPlugin):
    """
    Export identified vulnerabilities to a JSON file.

    :author: jose nazario (jose@monkey.org)
    """

    def __init__(self):
        OutputPlugin.__init__(self)
        self.output_file = "~/output-w3af.json"
        self._timestamp = str(int(time.time()))
        self._long_timestamp = str(time.strftime(TIME_FORMAT, time.localtime()))

        # Set defaults for scan metadata
        self._plugins_dict = {}
        self._options_dict = {}
        self._enabled_plugins = {}

    def do_nothing(self, *args, **kwargs):
        pass

    debug = log_http = vulnerability = do_nothing
    information = error = console = do_nothing

    def end(self):
        self.flush()

    def log_enabled_plugins(self, plugins_dict, options_dict):
        """
        This method is called from the output manager object. This method
        should take an action for the enabled plugins and their configuration.
        Usually, write the info to a file or print it somewhere.

        :param plugins_dict: A dict with all the plugin types and the
                                enabled plugins for that type of plugin.
        :param options_dict: A dict with the options for every plugin.
        """
        # TODO: Improve so it contains the plugin configuration too
        for plugin_type, enabled in plugins_dict.items():
            self._enabled_plugins[plugin_type] = enabled

    def flush(self):
        """
        Exports the vulnerabilities and information to the user configured
        file.
        """
        self.output_file = os.path.expanduser(self.output_file)

        configuration = self.get_configuration()
        target_urls = [t.url_string for t in configuration.get("targets")]

        target_domain = "unknown"
        target_domains = configuration.get("target_domains")
        if target_domains:
            target_domain = target_domains[0]

        enabled_plugins = self._enabled_plugins

        try:
            with open(self.output_file, "w", encoding="utf-8") as output_handler:
                self._write_report(
                    output_handler,
                    target_urls,
                    target_domain,
                    enabled_plugins,
                )
        except OSError as ioe:
            msg = 'Failed to open the output file for writing: "%s"'
            self._output.error(msg % ioe)

    def _write_report(
        self, output_handler, target_urls, target_domain, enabled_plugins
    ):
        output_handler.write("{\n")
        self._write_field(
            output_handler, "w3af-version", get_w3af_version.get_w3af_version()
        )
        output_handler.write('    "scan-info": {\n')
        self._write_field(output_handler, "target_urls", target_urls, indent=8)
        self._write_field(output_handler, "target_domain", target_domain, indent=8)
        self._write_field(output_handler, "enabled_plugins", enabled_plugins, indent=8)
        self._write_field(
            output_handler,
            "findings",
            self._iter_finding_descriptions(),
            indent=8,
            array=True,
        )
        self._write_field(
            output_handler,
            "known_urls",
            (str(url) for url in self._get_knowledge_base().get_all_known_urls()),
            indent=8,
            array=True,
            trailing_comma=False,
        )
        output_handler.write("\n    },\n")
        self._write_field(output_handler, "start", self._timestamp)
        self._write_field(output_handler, "start-long", self._long_timestamp)
        self._write_field(
            output_handler,
            "items",
            self._iter_finding_items(),
            array=True,
            trailing_comma=False,
        )
        output_handler.write("\n}\n")

    def _write_field(
        self,
        output_handler,
        name,
        value,
        *,
        indent=4,
        array=False,
        trailing_comma=True,
    ):
        output_handler.write(" " * indent)
        json.dump(name, output_handler)
        output_handler.write(": ")
        if array:
            self._write_array(output_handler, value)
        else:
            json.dump(value, output_handler)
        output_handler.write(",\n" if trailing_comma else "")

    @staticmethod
    def _write_array(output_handler, values):
        output_handler.write("[")
        for index, value in enumerate(values):
            if index:
                output_handler.write(",")
            json.dump(value, output_handler)
        output_handler.write("]")

    def _iter_finding_descriptions(self):
        for finding in self._get_knowledge_base().get_all_findings_iter():
            description = getattr(finding, "_desc", None)
            if description:
                yield description

    def _iter_finding_items(self):
        for info in self._get_knowledge_base().get_all_findings_iter():
            post_data = info.get_mutant().get_data().encode("utf-8")
            yield {
                "Severity": info.get_severity(),
                "Name": info.get_name(),
                "HTTP method": info.get_method(),
                "URL": str(info.get_url()),
                "Vulnerable parameter": info.get_token_name(),
                "POST data": base64.b64encode(post_data).decode("ascii"),
                "Vulnerability IDs": info.get_id(),
                "CWE IDs": getattr(info, "cwe_ids", []),
                "WASC IDs": getattr(info, "wasc_ids", []),
                "Tags": getattr(info, "tags", []),
                "VulnDB ID": info.get_vulndb_id(),
                "Description": info.get_desc(),
            }

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        return """
        This plugin exports all identified vulnerabilities to a JSON file.
        
        Each report contains information about the scan
          * w3af-version
          * Start time
          * Known URLs
          * Enabled plugins
          * Target URLs
          * Target domain
          * Findings
        
        Each finding in the sequence contains the following fields:
          * Severity
          * Name
          * HTTP method
          * URL
          * Vulnerable parameter
          * Base64 encoded POST-data
          * Unique vulnerability ID
          * CWE IDs
          * WASC IDs
          * Tags
          * VulnDB ID
          * Severity
          * Description
            
        The JSON plugin should be used for quick and easy integrations with w3af,
        external tools which require more details, such as the HTTP request and
        response associated with each vulnerability, should use the xml_file
        output plugin.
        
        One configurable parameter exists:
            - output_file
        """

    def set_options(self, option_list):
        """
        Sets the Options given on the OptionList to self. The options are the
        result of a user entering some data on a window that was constructed
        using the XML Options that was retrieved from the plugin using
        get_options()
        :return: No value is returned.
        """
        self.output_file = option_list["output_file"].get_value()

    def get_options(self):
        """
        :return: A list of option objects for this plugin.
        """
        ol = OptionList()

        d = "The name of the output file where the vulnerabilities are be saved"
        o = opt_factory("output_file", self.output_file, d, OUTPUT_FILE)
        ol.add(o)

        return ol
