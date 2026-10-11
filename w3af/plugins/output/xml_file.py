"""
xml_file.py

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
import shutil
import time
from functools import wraps
from tempfile import NamedTemporaryFile

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from w3af import ROOT_PATH
from w3af.core.controllers.misc import get_w3af_version
from w3af.core.controllers.plugins.output_plugin import OutputPlugin
from w3af.core.data.constants.encodings import DEFAULT_ENCODING
from w3af.core.data.db.disk_list import DiskList
from w3af.core.data.db.url_tree import URLTree
from w3af.core.data.misc.dotdict import dotdict
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.options.option_types import OUTPUT_FILE
from w3af.plugins.output.xml_filters import (
    ATTR_VALUE_ESCAPES,
    ATTR_VALUE_ESCAPES_IGNORE,
    TEXT_VALUE_ESCAPES,
    TEXT_VALUE_ESCAPES_IGNORE,
    is_unicode_escape,
    jinja2_attr_value_escape_filter,
    jinja2_text_value_escape_filter,
)
from w3af.plugins.output.xml_models import (
    Finding,
    HTTPTransaction,
    ScanInfo,
    ScanStatus,
)
from w3af.plugins.output.xml_nodes import CachedXMLNode, FindingsCache, XMLNode

__all__ = [
    "ATTR_VALUE_ESCAPES",
    "ATTR_VALUE_ESCAPES_IGNORE",
    "TEXT_VALUE_ESCAPES",
    "TEXT_VALUE_ESCAPES_IGNORE",
    "CachedXMLNode",
    "Finding",
    "FindingsCache",
    "HTTPTransaction",
    "ScanInfo",
    "ScanStatus",
    "XMLNode",
    "is_unicode_escape",
    "jinja2_attr_value_escape_filter",
    "jinja2_text_value_escape_filter",
    "took",
    "xml_file",
]

TIME_FORMAT = "%a %b %d %H:%M:%S %Y"

TEMPLATE_ROOT = os.path.join(ROOT_PATH, "plugins/output/xml_file/")


def took(func):
    """
    A decorator that will print how long a function was running
    to the debug output. This is useful for measuring performance
    in production.
    """

    @wraps(func)
    def func_wrapper(*args, **kwargs):
        start = time.time()

        result = func(*args, **kwargs)

        spent = time.time() - start

        # Log things which take more than 0.5 seconds
        if spent > 0.5:
            output = getattr(args[0], "_output", None)
            if output is not None:
                msg = "[xml_file.flush()] %s took %.2f seconds to run."
                function_name = func.__name__
                args = (function_name, spent)
                output.debug(msg % args)

        return result

    return func_wrapper


class xml_file(OutputPlugin):
    """
    Print all messages to a xml file.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    uses_database = True
    XML_OUTPUT_VERSION = "2.8"

    def __init__(self, db=None):
        OutputPlugin.__init__(self)

        # User configured parameters
        self._file_name = "~/report.xml"
        self._timestamp = str(int(time.time()))
        self._long_timestamp = str(time.strftime(TIME_FORMAT, time.localtime()))

        # Set defaults for scan metadata
        self._plugins_dict = {}
        self._options_dict = {}
        self._scan_targets = None

        # Keep internal state
        self._is_working = False
        self._jinja2_env = self._get_jinja2_env()
        self._db = db

        # List with additional xml elements
        self._errors = DiskList(db=db)

    def do_nothing(self, *args, **kwds):
        pass

    debug = information = vulnerability = console = log_http = do_nothing

    def error(self, message, new_line=True):
        """
        This method is called from the output object. The output object was
        called from a plugin or from the framework. This method should take an
        action for error messages.
        """
        #
        # Note that while the call to "get_caller()" is costly, it only happens
        # when an error occurs, so it shouldn't impact performance
        #
        error_data = (message, self.get_caller())
        self._errors.append(error_data)

    def set_options(self, option_list):
        """
        Sets the Options given on the OptionList to self. The options are the
        result of a user entering some data on a window that was constructed
        using the XML Options that was retrieved from the plugin using
        get_options()

        This method MUST be implemented on every plugin.

        :return: No value is returned.
        """
        self._file_name = option_list["output_file"].get_value()

    def get_options(self):
        """
        :return: A list of option objects for this plugin.
        """
        ol = OptionList()

        d = "Output file name where to write the XML data"
        o = opt_factory("output_file", self._file_name, d, OUTPUT_FILE)
        ol.add(o)

        return ol

    def log_enabled_plugins(self, plugins_dict, options_dict):
        """
        This method is called from the output manager object. This method should
        take an action for the enabled plugins and their configuration. Usually,
        write the info to a file or print it somewhere.

        :param plugins_dict: A dict with all the plugin types and the enabled
                             plugins for that type of plugin.
        :param options_dict: A dict with the options for every plugin.
        """
        # See doc for _log_enabled_plugins_to_xml to understand why we don't write
        # to the XML just now.
        self._plugins_dict = plugins_dict
        self._options_dict = options_dict

    def end(self):
        """
        This method is called when the scan has finished.
        """
        self.flush()

        # Free some memory and disk space
        self._plugins_dict = {}
        self._options_dict = {}
        self._scan_targets = None
        self._errors.cleanup()
        self._jinja2_env = None

    def flush(self):
        """
        Write the XML to the output file
        :return: None
        """
        # Create the cache path
        CachedXMLNode.create_cache_path()
        FindingsCache.create_cache_path()

        # Create the context
        context = dotdict({})

        try:
            self._add_scan_status_to_context(context)
        except RuntimeError as rte:
            # In some very strange scenarios we get this error:
            #
            #   Can NOT call get_run_time before start()
            #
            # Just "ignore" this call to flush and write the XML in the next call
            msg = 'xml_file.flush() failed to add scan status to context: "%s"'
            self._output.debug(msg % rte)
            return

        self._add_root_info_to_context(context)
        self._add_scan_info_to_context(context)
        self._add_findings_to_context(context)
        self._add_errors_to_context(context)

        # Write to file
        self._write_context_to_file(context)

    @took
    def _add_root_info_to_context(self, context):
        context.start_timestamp = self._timestamp
        context.start_time_long = self._long_timestamp
        context.xml_version = self.XML_OUTPUT_VERSION
        context.w3af_version = get_w3af_version.get_w3af_version()

    @took
    def _add_scan_info_to_context(self, context):
        if self._scan_targets is None:
            targets = self.get_configuration().get("targets")
            self._scan_targets = ",".join(t.url_string for t in targets)

        scan_info = ScanInfo(
            self._jinja2_env, self._scan_targets, self._plugins_dict, self._options_dict
        )
        context.scan_info = scan_info.to_string()

    @took
    def _add_scan_status_to_context(self, context):
        self._output.debug("[xml_file.flush()] _add_scan_status_to_context() start")

        status = self.get_w3af_core().status.get_status_as_dict()
        self._output.debug(
            "[xml_file.flush()] _add_scan_status_to_context() read status"
        )

        all_known_urls = self._get_knowledge_base().get_all_known_urls()
        total_urls = len(all_known_urls)
        self._output.debug(
            "[xml_file.flush()] _add_scan_status_to_context() read total_urls"
        )

        known_urls = self._get_known_urls(all_known_urls)
        self._output.debug(
            "[xml_file.flush()] _add_scan_status_to_context() read generated URLTree"
        )

        scan_status = ScanStatus(self._jinja2_env, status, total_urls, known_urls)
        context.scan_status = scan_status.to_string()
        self._output.debug("[xml_file.flush()] _add_scan_status_to_context() rendered")

    def _get_known_urls(self, all_known_urls):
        """
        This method calls kb.get_all_known_urls() to retrieve the URLs,
        then it structures them into a tree which has some helper methods
        to allow us to easily print them using jinja2 templates.

        :return: A URLTree instance
        """
        url_tree = URLTree()

        for url in all_known_urls:
            url_tree.add_url(url)

        return url_tree

    @took
    def _add_errors_to_context(self, context):
        context.errors = self._errors

    def findings(self):
        """
        A small generator that queries the findings cache and yields all the
        findings so they get written to the XML.

        :yield: Strings representing the findings as XML
        """
        cache = FindingsCache()
        cached_nodes = cache.list()

        processed_uniq_ids = []

        self._output.debug("[xml_file.flush()] Starting findings()")
        start = time.time()

        #
        # This for loop is a performance improvement which should yield
        # really good results, taking into account that get_all_uniq_ids_iter
        # will only query the DB and yield IDs, without doing any of the
        # CPU-intensive cPickle.loads() done in get_all_findings_iter()
        # which we do below.
        #
        # Ideally, we're only doing a cPickle.loads() once for each finding
        # the rest of the calls to flush() will load the finding from the
        # cache in this loop, and use the exclude_ids to prevent cached
        # entries from being queried
        #
        # What this for loop also guarantees is that we're not simply
        # reading all the items from the cache and putting them into the XML,
        # which would be incorrect because some items are modified in the
        # KB (which changes their uniq id)
        #
        for uniq_id in self._get_knowledge_base().get_all_uniq_ids_iter(
            include_ids=cached_nodes
        ):
            node = cache.get_node_from_cache(uniq_id)

            # cached_nodes can be (), this means that get_all_uniq_ids_iter()
            # will return *all* findings, some might not be in the cache. When
            # that happens, the cache returns None
            if node is not None:
                yield node
                processed_uniq_ids.append(uniq_id)

        msg = "[xml_file.flush()] findings() processed %s cached nodes in %.2f seconds"
        spent = time.time() - start
        args = (len(processed_uniq_ids), spent)
        self._output.debug(msg % args)

        start = time.time()

        #
        # This for loop is getting all the new findings that w3af has found
        # In this context "new" means that the findings are not in the cache
        #
        new_findings = 0

        for finding in self._get_knowledge_base().get_all_findings_iter(
            exclude_ids=cached_nodes
        ):
            uniq_id = finding.get_uniq_id()
            processed_uniq_ids.append(uniq_id)
            core = self.get_w3af_core()
            database = self._db if core is None else core.database
            node = Finding(
                self._jinja2_env,
                finding,
                self._output,
                db=database,
            ).to_string()
            cache.save_finding_to_cache(uniq_id, node)

            new_findings += 1

            yield node

        msg = "[xml_file.flush()] findings() processed %s new findings in %.2f seconds"
        spent = time.time() - start
        args = (new_findings, spent)
        self._output.debug(msg % args)

        start = time.time()

        #
        # Now that we've finished processing all the new findings we can
        # evict the findings that were removed from the KB from the cache
        #
        evicted_findings = 0

        for cached_finding in cached_nodes:
            if cached_finding not in processed_uniq_ids:
                cache.evict_from_cache(cached_finding)

                evicted_findings += 1

        msg = "[xml_file.flush()] findings() evicted %s findings from cache in %.2f seconds"
        spent = time.time() - start
        args = (evicted_findings, spent)
        self._output.debug(msg % args)

    @took
    def _add_findings_to_context(self, context):
        context.findings = (f for f in self.findings())

    def _get_jinja2_env(self):
        """
        Creates the jinja2 environment which will be used to render all templates

        The same environment is used in order to take advantage of jinja's template
        cache.

        :return: A jinja2 environment
        """
        env_config = {
            "undefined": StrictUndefined,
            "trim_blocks": True,
            "lstrip_blocks": True,
        }

        jinja2_env = Environment(autoescape=True, **env_config)
        jinja2_env.loader = FileSystemLoader(TEMPLATE_ROOT)
        jinja2_env.filters["escape_attr"] = jinja2_attr_value_escape_filter
        jinja2_env.filters["escape_text"] = jinja2_text_value_escape_filter
        return jinja2_env

    @took
    def _write_context_to_file(self, context):
        """
        Write xml report to the file by rendering the context
        :return: None
        """
        self._output.debug("[xml_file.flush()] Starting _write_context_to_file()")

        template = self._jinja2_env.get_template("root.tpl")

        # We use streaming as explained here:
        #
        # http://flask.pocoo.org/docs/0.12/patterns/streaming/
        #
        # To prevent having the whole XML in memory
        report_stream = template.stream(context)
        report_stream.enable_buffering(3)

        # Write everything to a temp file, this is useful in two cases:
        #
        #   * An external tool will always see a valid XML in the output,
        #     and not just a partially written XML document.
        #
        #   * If w3af is killed in the middle of writing the XML report,
        #     the report file will still be valid -- if xml_file.flush() was
        #     run successfully at least once
        with NamedTemporaryFile(
            delete=False, prefix="w3af-xml-output", suffix=".xml"
        ) as tempfh:
            self._output.debug(
                "[xml_file.flush()] write_context_to_file() created"
                " template.stream and NamedTemporaryFile"
            )

            # Write each report section to the temp file. Closing the temp file
            # (done when leaving this with block) flushes all the content.
            for report_section in report_stream:
                tempfh.write(report_section.encode(DEFAULT_ENCODING))

        try:
            self._output.debug(
                "[xml_file.flush()] write_context_to_file() starting to"
                " copy temp file to destination"
            )

            # Copy to the real output file
            report_file_name = os.path.expanduser(self._file_name)

            shutil.copyfile(tempfh.name, report_file_name)

            self._output.debug(
                "[xml_file.flush()] write_context_to_file() finished copy" " operation."
            )

            stat_info = os.stat(report_file_name)
            self._output.debug(
                f"The XML output file size is {stat_info.st_size} bytes."
            )

        finally:
            os.remove(tempfh.name)

        self._output.debug("[xml_file.flush()] write_context_to_file() finished")

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        return """
        This plugin creates an XML file containing all of w3af's findings.

        One configurable parameter exists:
            - output_file

        When using the contents of the XML file it's important to notice that
        the long-description and fix-guidance tags contain text in markdown
        format.

        The generated XML file validates against the report.xsd file which is
        distributed with the plugin.
        
        Some vulnerabilities require special characters to be triggered, those
        special characters might not be valid according to the XML specification,
        in order to be able to write these to the report, tags like the following
        are used:
        
            <character code="hhhh"/>
        
        Where "hhhh" is the hex representation of the character. The XML parser
        should handle these tags and show the real character to the user, encoded
        as expected in the final format. 
        """
