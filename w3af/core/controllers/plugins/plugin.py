"""
plugin.py

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

import queue
import threading
from itertools import repeat
from typing import Any

from tblib.decorators import Error

from w3af.core.configurable import Configurable
from w3af.core.controllers.threads.decorators import apply_with_return_error
from w3af.core.controllers.threads.threadpool import return_args
from w3af.core.data.kb.info import Info
from w3af.core.data.kb.info_set import InfoSet
from w3af.core.data.misc.number_generator import NumberGenerator
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.helpers import new_no_content_resp
from w3af.core.exceptions import BaseFrameworkException


class Plugin(Configurable):
    """
    This is the base class for ALL plugins, all plugins should inherit from it
    and implement the following method :
        1. get_plugin_deps()

    Please note that this class is a configurable object, so it must implement:
        1. set_options( OptionList )
        2. get_options()

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    uses_database = False

    def __init__(self):
        """
        Create some generic attributes that are going to be used by most plugins
        """
        self._uri_opener: Any = None
        self._w3af_core = None
        self._configuration = None
        self._knowledge_base = None
        self._parser_cache = None
        self._id_generator = NumberGenerator()
        self._fingerprint_404 = None
        self._output: Any = None
        self.worker_pool: Any = None

        self.output_queue: queue.Queue[FuzzableRequest] = queue.Queue()
        self._plugin_lock = threading.RLock()

    def set_worker_pool(self, worker_pool):
        """
        Sets the worker pool (at the moment of writing this is a thread pool)
        that will be used by the plugin to send requests using different
        threads.
        """
        self.worker_pool = worker_pool

    def set_url_opener(self, url_opener):
        """
        This method should not be overwritten by any plugin (but you are free
        to do it, for example a good idea is to rewrite this method to change
        the UrlOpener to do some IDS evasion technique).

        This method takes a CustomUrllib object as parameter and assigns it
        to itself. Then, on the testUrl method you use
        self.CustomUrlOpener._custom_urlopen(...)
        to open a Url and you are sure that the plugin is using the user
        supplied settings (proxy, user agent, etc).

        :return: No value is returned.
        """
        self._uri_opener = UrlOpenerProxy(url_opener, self)

    def set_w3af_core(self, w3af_core):
        """
        Set the w3af core instance to the plugin. This shouldn't be used much
        but it is helpful when the plugin needs to query something about the
        core status.

        :return: None
        """
        self._w3af_core = w3af_core

    def set_configuration(self, configuration):
        """Set the scan configuration used by plugin-level helpers."""
        self._configuration = configuration

    def get_configuration(self):
        if self._configuration is None:
            raise RuntimeError("Plugin requires a configured scan configuration")
        return self._configuration

    def set_knowledge_base(self, knowledge_base):
        """Set the knowledge store used by this plugin."""
        self._knowledge_base = knowledge_base

    def set_parser_cache(self, parser_cache):
        """Set the parser cache used by this plugin."""
        self._parser_cache = parser_cache

    def set_id_generator(self, id_generator):
        """Set the ID generator used by this plugin."""
        self._id_generator = id_generator

    def set_fingerprint_404(self, fingerprint_404):
        """Set the 404 detector used by standalone plugin instances."""
        self._fingerprint_404 = fingerprint_404

    def set_output(self, output):
        """Set the output sink used by this plugin."""
        self._output = output

    def _get_knowledge_base(self):
        if self._knowledge_base is None:
            raise RuntimeError("Plugin knowledge base has not been configured")
        return self._knowledge_base

    def _get_parser_cache(self):
        if self._parser_cache is None:
            raise RuntimeError("Plugin parser cache has not been configured")
        return self._parser_cache

    def _get_clear_text_body(self, response):
        try:
            parser = self._get_parser_cache().get_document_parser_for(response)
        except BaseFrameworkException:
            return ""

        return parser.get_clear_text_body()

    def get_w3af_core(self):
        return self._w3af_core

    def _is_404(self, http_response):
        if self._w3af_core is not None:
            return self._w3af_core.is_404(http_response)
        if self._fingerprint_404 is None:
            raise RuntimeError("Plugin requires a configured 404 detector")
        return self._fingerprint_404.is_404(http_response)

    def set_options(self, options_list):
        """
        Sets the Options given on the OptionList to self. The options are the
        result of a user entering some data on a window that was constructed
        using the options that were retrieved from the plugin using
        get_options()

        This method must be implemented in every plugin that wishes to have user
        configurable options.

        :return: No value is returned.
        """

    def get_options(self):
        """
        :return: A list of option objects for this plugin.
        """
        ol = OptionList()
        return ol

    def get_plugin_deps(self):
        """
        :return: A list with the names of the plugins that should be
                 run before the current one. Only plugins with dependencies
                 should override this method.
        """
        return []

    def get_desc(self):
        """
        :return: A description of the plugin.
        """
        if self.__doc__ is not None:
            tmp = self.__doc__.replace("    ", "")

            res = "".join(
                line
                for line in tmp.split("\n")
                if line != "" and not line.startswith(":")
            )
        else:
            res = "No description available for this plugin."
        return res

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        msg = "Plugin is not implementing required method get_long_desc"
        raise NotImplementedError(msg)

    def kb_append_uniq(self, location_a, location_b, info, filter_by="VAR"):
        """
        kb.kb.append_uniq a vulnerability to the KB
        """
        self._configure_info(info)
        added_to_kb = self._get_knowledge_base().append_uniq(
            location_a, location_b, info, filter_by=filter_by
        )

        if added_to_kb:
            output = self._output
            if output is None:
                raise RuntimeError("Plugin output has not been configured")
            output.report_finding(info)

        return added_to_kb

    def kb_append_uniq_group(self, location_a, location_b, info, group_klass=InfoSet):
        """
        kb.kb.append_uniq_group a vulnerability to the KB
        """
        self._configure_info(info)
        info_set, created = self._get_knowledge_base().append_uniq_group(
            location_a, location_b, info, group_klass=group_klass
        )

        if created:
            output = self._output
            if output is None:
                raise RuntimeError("Plugin output has not been configured")
            output.report_finding(info_set.first_info)

    def kb_append(self, location_a, location_b, info):
        """
        kb.kb.append a vulnerability to the KB
        """
        self._kb_append(location_a, location_b, info)
        output = self._output
        if output is None:
            raise RuntimeError("Plugin output has not been configured")
        output.report_finding(info)

    def _kb_append(self, location_a, location_b, value):
        """Store a KB value while applying scan configuration to findings."""
        self._configure_info(value)
        self._get_knowledge_base().append(location_a, location_b, value)

    def _configure_info(self, info):
        if self._configuration is not None and isinstance(info, Info):
            info.set_configuration(self._configuration)

    def __eq__(self, other):
        """
        This function is called when extending a list of plugin instances.
        """
        return self.__class__.__name__ == other.__class__.__name__

    def __hash__(self):
        return hash(self.__class__.__name__)

    def __repr__(self):
        return f"<{self.get_type()}.{self.get_name()}>"

    def end(self):
        """
        This method is called by w3afCore to let the plugin know that it wont
        be used anymore. This is helpful to do some final tests, free some
        structures, etc.
        """

    def get_type(self):
        return "plugin"

    def get_name(self):
        return self.__class__.__name__

    def _send_mutants_in_threads(self, func, iterable, callback, **kwds):
        """
        Please note that this method blocks from the caller's point of view
        but performs all the HTTP requests in parallel threads.

        :param func: The function to use to send the mutants
        :param iterable: A list with the mutants
        :param callback: A callable to invoke after each mutant is sent
        """
        worker_pool = self.worker_pool
        if worker_pool is None:
            raise RuntimeError("Plugin worker pool has not been configured")
        output = self._output
        if output is None:
            raise RuntimeError("Plugin output has not been configured")

        imap_unordered = worker_pool.imap_unordered
        awre = apply_with_return_error

        try:
            num_tasks = len(iterable)
        except TypeError:
            # When the iterable is a python iterator which doesn't implement
            # the __len__, then we don't know the number of received tasks
            pass
        else:
            debugging_id = kwds.get("debugging_id", "unknown")
            msg = "send_mutants_in_threads will send %s HTTP requests (did:%s)"
            debug_args = (num_tasks, debugging_id)
            output.debug(msg % debug_args)

        # You can use this code to debug issues that happen in threads, by
        # simply not using them:
        #
        # for i in iterable:
        #    callback(i, func(i))
        # return
        #
        # Now the real code:
        func = return_args(func, **kwds)
        task_args = list(zip(repeat(func), iterable))

        for result in imap_unordered(awre, task_args):
            # re-raise the thread exception in the main thread with this method
            # so we get a nice traceback instead of things like the ones we see
            # in https://github.com/andresriancho/w3af/issues/7286
            if isinstance(result, Error):
                result.reraise()
            else:
                (mutant,), http_response = result
                callback(mutant, http_response)

    def handle_url_error(self, uri, http_exception):
        """
        Handle UrlError exceptions raised when requests are made.
        Subclasses should redefine this method for a more refined
        behavior and must respect the return value format.

        :param http_exception: HTTPRequestException exception instance

        :return: A tuple containing:
            * re_raise: Boolean value that indicates the caller if the original
                        exception should be re-raised after this error handling
                        method.

            * result: The result to be returned to the caller. This only makes
                      sense if re_raise is False.
        """
        no_content_resp = new_no_content_resp(
            uri, add_id=True, id_generator=self._id_generator
        )

        msg = (
            'The %s plugin got an error while requesting "%s".'
            ' Exception: "%s".'
            ' Generated 204 "No Content" response (id:%s)'
        )
        output = self._output
        if output is None:
            raise RuntimeError("Plugin output has not been configured")
        error_args = (self.get_name(), uri, http_exception, no_content_resp.id)
        output.error(msg % error_args)

        return False, no_content_resp


class UrlOpenerProxy:
    """
    Proxy class for urlopener objects such as ExtendedUrllib instances.
    """

    # I want to list all the methods which I do NOT want to wrap, I have to
    # do it this way since the extended_urllib.py also implements __getattr__
    # to provide PUT, PATCH, etc. methods.
    #
    # These methods won't be wrapped, mostly because they either:
    #   * Don't return an HTTPResponse
    #   * Don't raise HTTPRequestException
    #
    # I noticed this issue when #8705 was reported
    # https://github.com/andresriancho/w3af/issues/8705
    NO_WRAPPER_FOR = frozenset(
        {
            "send_clean",
            "clear",
            "end",
            "restart",
            "get_cookies",
            "add_headers",
            "assert_allowed_proto",
            "get_average_rtt_for_mutant",
            "_handle_send_socket_error",
            "_handle_send_urllib_error",
            "_handle_send_success",
            "_handle_error_on_increment",
            "_generic_send_error_handler",
            "_increment_global_error_count",
            "_log_successful_response",
        }
    )

    def __init__(self, url_opener, plugin_inst):
        self._url_opener = url_opener
        self._plugin_inst = plugin_inst

    def __getattr__(self, name):

        attr = getattr(self._url_opener, name)

        def url_opener_proxy(*args, **kwargs):
            try:
                return attr(*args, **kwargs)
            except HTTPRequestException as hre:
                #
                # We get here when **one** HTTP request fails. When more than
                # one exception fails the URL opener will raise a different
                # type of exception (not a subclass of HTTPRequestException)
                # and that one will bubble up to w3afCore/strategy/etc.
                #
                arg1 = args[0]
                if hasattr(arg1, "get_uri"):
                    # Mutants and fuzzable requests enter here
                    uri = arg1.get_uri()
                else:
                    # It was a URL instance
                    uri = arg1

                re_raise, result = self._plugin_inst.handle_url_error(uri, hre)

                # By default we do NOT re-raise, we just return a 204-no content
                # response and hope for the best.
                if re_raise:
                    raise

                return result

        if name in self.NO_WRAPPER_FOR:
            # See note above on NO_WRAPPER_FOR
            return attr
        elif callable(attr):
            return url_opener_proxy
        else:
            return attr
