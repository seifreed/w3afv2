"""
extended_urllib.py

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

import functools
import http.client
import logging
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.client import BadStatusLine

import OpenSSL

import w3af.core.data.kb.config as cf
from w3af.core.data.fuzzer.utils import rand_alnum
from w3af.core.data.misc.lru import SynchronizedLRUDict
from w3af.core.data.misc.number_generator import consecutive_number_generator
from w3af.core.data.parsers.doc.http_request_parser import http_request_parser
from w3af.core.data.url.constants import (
    MAX_ERROR_COUNT,
    TIMEOUT_ADJUST_LIMIT,
)
from w3af.core.data.url.exceptions import ConnectionPoolException, HTTPRequestException
from w3af.core.data.url.failed_response_recorder import FailedResponseRecorder
from w3af.core.data.url.get_average_rtt import GetAverageRTTForMutant
from w3af.core.data.url.grep_dispatcher import GrepDispatcher
from w3af.core.data.url.handlers.keepalive import URLTimeoutError
from w3af.core.data.url.helpers import get_clean_body, get_exception_reason
from w3af.core.data.url.http_error_pause_controller import HttpErrorPauseController
from w3af.core.data.url.rate_limiter import RateLimiter
from w3af.core.data.url.request_builder import RequestBuilder
from w3af.core.data.url.request_error_handler import RequestErrorHandler
from w3af.core.data.url.request_evasion import RequestEvasionPipeline
from w3af.core.data.url.request_preparer import RequestPreparer
from w3af.core.data.url.request_retry_handler import RequestRetryHandler
from w3af.core.data.url.response_history import ResponseHistory
from w3af.core.data.url.response_success_handler import ResponseSuccessHandler
from w3af.core.data.url.scan_request_control import ScanRequestControl
from w3af.core.data.url.server_reachability_checker import ServerReachabilityChecker
from w3af.core.data.url.session_lifecycle import SessionLifecycle
from w3af.core.data.url.size_limit_override import SizeLimitOverride
from w3af.core.data.url.timeout_adjustment_policy import TimeoutAdjustmentPolicy
from w3af.core.data.url.timeout_manager import TimeoutManager
from w3af.core.data.url.worker_pool_adjuster import WorkerPoolAdjuster
from w3af.core.exceptions import (
    ScanMustStopByKnownReasonExc,
    ScanMustStopByUnknownReasonExc,
)

from . import opener_settings

LOGGER = logging.getLogger(__name__)


class ExtendedUrllib:
    """
    This is a urllib2 wrapper.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    def __init__(self, http_log_callback=None, sleep=time.sleep):
        self.settings = opener_settings.OpenerSettings(http_log_callback)
        self._sleep = sleep
        self._average_rtt_mutant = GetAverageRTTForMutant(self)

        # In exploit mode we disable some timeout/delay/error handling stuff
        self.exploit_mode = False

        # For error handling, the history starts with successful responses so
        # the unreachable-server pattern can be detected from the first errors.
        self._response_history = ResponseHistory()
        self._count_lock = threading.RLock()

        # For rate limiting and timeouts
        self._rate_limiter = RateLimiter(self.settings, sleep)
        self._timeout_manager = TimeoutManager(self.settings)
        self._size_limit_override = SizeLimitOverride(cf.cf)
        self._timeout_adjustment = TimeoutAdjustmentPolicy(
            self._timeout_manager,
            self.get_average_rtt,
            self.get_total_requests,
            self.set_timeout,
            self.get_timeout,
            LOGGER.debug,
        )

        # Keep track of sum(rtt) for each debugging_id
        self._rtt_sum_debugging_id = SynchronizedLRUDict(capacity=128)

        # For timeout auto adjust and general stats
        self._total_requests = 0

        self._worker_pool_adjuster = WorkerPoolAdjuster(
            self.get_error_rate,
            LOGGER.debug,
        )

        # Timeout is kept by host
        # Used in the pause on HTTP error feature to keep track of when the
        # core slept waiting for the remote end to be reachable
        self._error_pause_controller = HttpErrorPauseController(
            self.get_error_rate,
            self.get_total_requests,
            self._sleep,
            LOGGER.debug,
        )

        # User configured options (in an indirect way)
        self._grep_dispatcher = GrepDispatcher()
        self._evasion_pipeline = RequestEvasionPipeline(LOGGER.error)
        self._request_preparer = RequestPreparer(self.settings)
        self._request_builder = RequestBuilder(
            lambda: self.settings,
            self.setup,
            self.get_timeout,
            self.add_headers,
        )
        self._response_success_handler = ResponseSuccessHandler(
            LOGGER.debug,
            self._log_successful_response,
            self._track_rtt,
            self._worker_pool_adjuster.adjust,
            self._grep,
        )
        self._retry_handler = RequestRetryHandler(
            self.send,
            self.get_timeout,
            LOGGER.debug,
        )
        self._failed_response_recorder = FailedResponseRecorder(
            self._response_history,
            self.get_timeout,
            self._log_error_rate,
            LOGGER.debug,
        )
        self._error_handler = RequestErrorHandler(
            LOGGER.debug,
            self._increase_timeout_on_error,
            self._count_lock,
            self._log_failed_response,
            self._should_stop_scan,
            self._handle_error_count_exceeded,
            self._worker_pool_adjuster.adjust,
            self._retry,
        )
        self._reachability_checker = ServerReachabilityChecker(
            self.get_timeout,
            self.set_timeout,
            self.add_headers,
            self.send,
            LOGGER.debug,
        )
        self._request_control = ScanRequestControl()
        self._session_lifecycle = SessionLifecycle(
            lambda: self.settings,
            self._request_control,
            self._response_history,
            self._reset_total_requests,
            lambda: self.set_exploit_mode(False),
            self.clear_timeout,
        )

    @property
    def _opener(self):
        return self._session_lifecycle.opener

    def get_average_rtt_for_mutant(self, *args, **kwargs):
        return self._average_rtt_mutant.get_average_rtt_for_mutant(*args, **kwargs)

    def pause(self, pause_yes_no):
        """
        When the core wants to pause a scan, it calls this method, in order to
        freeze all actions

        :param pause_yes_no: True if I want to pause the scan;
                             False to un-pause it.
        """
        self._request_control.pause(pause_yes_no)

    def stop(self):
        """
        Called when the user wants to finish a scan.
        """
        self._request_control.stop()

    @property
    def _stop_exception(self):
        return self._request_control.stop_exception

    @_stop_exception.setter
    def _stop_exception(self, exception):
        self._request_control.stop_exception = exception

    def set_worker_pool_provider(self, provider, min_workers, max_workers):
        self._worker_pool_adjuster.configure(provider, min_workers, max_workers)

    def _before_send_hook(self, request):
        """
        This is a method that is called before every request is sent. I'm using
        it as a hook implement:
            - The pause/stop feature
            - Memory debugging features
        """
        # Handle errors (HTTP timeout, etc.)
        self._request_control.raise_if_should_stop()

        self._request_control.pause_and_stop()
        self._error_pause_controller.pause_on_error(request)

        if not self.exploit_mode:
            self._rate_limit()
            self._auto_adjust_timeout(request)

        # Increase the request count
        self._total_requests += 1

        # If the request has no debugging_id, then we add one here
        # this is useful for tracking any errors and retries generated by
        # the request
        if request.debugging_id is None:
            request.debugging_id = rand_alnum(8)

    def set_exploit_mode(self, exploit_mode):
        self.exploit_mode = exploit_mode

        # Set the timeout to DEFAULT_TIMEOUT
        self.clear_timeout()

        # Closes all HTTPConnections so all new requests are sent using the
        # DEFAULT_TIMEOUT
        self.settings.close_connections()

    def set_timeout(self, timeout, host):
        """
        Sets the timeout to use in HTTP requests, usually called by the auto
        timeout adjust feature in extended_urllib.py
        """
        msg = "Updating socket timeout for %s from %.2f to %.2f seconds"
        LOGGER.debug(msg, host, self.get_timeout(host), timeout)
        self._timeout_manager.set_timeout(timeout, host)

    def get_timeout(self, host):
        """
        :return: The timeout to use in HTTP requests, will be equal to the user
                 configured setting if the auto timeout adjust feature is
                 disabled, but when enabled this value will change during the
                 scan.
        """
        return self._timeout_manager.get_timeout(host)

    def clear_timeout(self):
        """
        Called when the scan has finished/this opener settings won't be used
        anymore.

        :return: None
        """
        self._timeout_manager.clear()

    def _auto_adjust_timeout(self, request):
        self._timeout_adjustment.adjust(request)

    def _increase_timeout_on_error(self, request, exception):
        self._timeout_adjustment.increase_after_error(request, exception)

    def get_average_rtt(self, count=TIMEOUT_ADJUST_LIMIT, host=None):
        """
        :param count: The number of HTTP requests to sample the RTT from
        :param host: If specified filter the requests by host before calculating
                     the average RTT
        :return: Tuple with (average RTT from the last `count` requests,
                             the number of successful responses, which contain
                             an RTT, and were used to calculate the average RTT)
        """
        return self._response_history.get_average_rtt(count, host)

    def get_total_requests(self):
        """
        :return: The number of requests sent (successful, timeout, failed, all
                 are counted here).
        """
        return self._total_requests

    @property
    def _sleep_log(self):
        return self._error_pause_controller.sleep_log

    def _rate_limit(self):
        """
        Makes sure that we don't send more than X HTTP requests per seconds
        :return:
        """
        self._rate_limiter.wait()

    def clear(self):
        self._session_lifecycle.clear()

    def end(self):
        self._session_lifecycle.end()

    def restart(self):
        self._session_lifecycle.restart()

    def setup(self):
        self._session_lifecycle.setup()

    def _reset_total_requests(self):
        self._total_requests = 0

    def get_cookies(self):
        """
        :return: The cookies that this uri opener has collected during this scan
        """
        return self.settings.get_cookies()

    def get_new_session(self):
        return str(uuid.uuid4())

    def send_clean(self, mutant, debugging_id=None, grep=True):
        """
        Sends a mutant to the network (without using the cache) and then returns
        the HTTP response object and a sanitized response body (which doesn't
        contain any traces of the injected payload).

        The sanitized version is useful for having clean comparisons between two
        responses that were generated with different mutants.

        :param mutant: The mutant to send to the network.
        :param debugging_id: A unique identifier for this call to audit()
        :return: (HTTP response, Sanitized HTTP response body)
        """
        http_response = self.send_mutant(
            mutant, cache=False, debugging_id=debugging_id, grep=grep
        )
        clean_body = get_clean_body(mutant, http_response)

        return http_response, clean_body

    def send_raw_request(self, head, postdata):
        """
        In some cases the ExtendedUrllib user wants to send a request that was
        typed in a textbox or is stored in a file. When something like that
        happens, this library allows the user to send the request by specifying
        two parameters for the send_raw_request method:

        :param head: "<method> <URI> <HTTP version>\r\nHeader: Value\r\n..."
        :param postdata: The data as string
                         If set to '' or None, no postdata is sent

        The Content-Length header in `head` is ignored (FuzzableRequest drops
        it), the length of the sent `postdata` is used instead.

        :return: An HTTPResponse object.
        """
        fuzz_req = http_request_parser(head, postdata)

        function_reference = getattr(self, fuzz_req.get_method())
        return function_reference(
            fuzz_req.get_uri(),
            data=fuzz_req.get_data(),
            headers=fuzz_req.get_headers(),
            cache=False,
            grep=False,
        )

    def send_mutant(
        self,
        mutant,
        callback=None,
        grep=True,
        cache=True,
        cookies=True,
        session=None,
        error_handling=True,
        timeout=None,
        follow_redirects=False,
        use_basic_auth=True,
        respect_size_limit=True,
        debugging_id=None,
        binary_response=False,
    ):
        """
        Sends a mutant to the remote web server.

        :param callback: If None, return the HTTP response object, else call
                         the callback with the mutant and the http response as
                         parameters.

        :param debugging_id: A unique identifier for this call to audit()

        :return: The HTTPResponse object associated with the request
                 that was just sent.
        """
        #
        # IMPORTANT NOTE: If you touch something here, the whole framework may
        # stop working!
        #
        uri = mutant.get_uri()
        data = mutant.get_data()
        headers = mutant.get_all_headers()

        # Also add the cookie header; this is needed by the CookieMutant
        if cookies:
            mutant_cookie = mutant.get_cookie()
            if mutant_cookie:
                headers["Cookie"] = str(mutant_cookie)

        args = (uri,)
        kwargs = {
            "data": data,
            "headers": headers,
            "grep": grep,
            "cache": cache,
            "cookies": cookies,
            "session": session,
            "error_handling": error_handling,
            "timeout": timeout,
            "follow_redirects": follow_redirects,
            "use_basic_auth": use_basic_auth,
            "respect_size_limit": respect_size_limit,
            "debugging_id": debugging_id,
            "binary_response": binary_response,
        }
        method = mutant.get_method()

        functor = getattr(self, method)
        res = functor(*args, **kwargs)

        if callback is not None:
            # The user specified a custom callback for analyzing the HTTP
            # response this is commonly used when sending requests in an
            # async way.
            callback(mutant, res)

        return res

    def GET(
        self,
        uri,
        data=None,
        headers=None,
        cache=False,
        grep=True,
        cookies=True,
        session=None,
        respect_size_limit=True,
        new_connection=False,
        error_handling=True,
        timeout=None,
        follow_redirects=False,
        use_basic_auth=True,
        use_proxy=True,
        debugging_id=None,
        binary_response=False,
    ):
        """
        HTTP GET a URI using a proxy, user agent, and other settings
        that where previously set in opener_settings.py .

        :param uri: This is the URI to GET, with the query string included.
        :param data: Object to send as post-data, usually a string or a data
                     container
        :param headers: Any special headers that will be sent with this request
        :param cache: Should the library search the local cache for a response
                      before sending it to the wire?
        :param grep: Should grep plugins be applied to this request/response?
        :param timeout: If None we'll use the configured (opener settings)
                        timeout or the auto-adjusted value. Otherwise we'll use
                        the defined timeout as the socket timeout value for this
                        request. The timeout is specified in seconds
        :param cookies: Send stored cookies in request (or not)
        :param session: The browser session / cookiejar to use in this request
        :param follow_redirects: Follow 30x redirects (or not)
        :param debugging_id: A unique identifier for this call to audit()

        :return: An HTTPResponse object.
        """
        req = self._request_builder.build_get(
            uri,
            data,
            headers,
            cache,
            cookies,
            session,
            error_handling,
            timeout,
            follow_redirects,
            use_basic_auth,
            use_proxy,
            debugging_id,
            new_connection,
            binary_response,
        )

        with self._size_limit_override.apply(respect_size_limit):
            return self.send(req, grep=grep)

    def POST(
        self,
        uri,
        data="",
        headers=None,
        grep=True,
        cache=False,
        cookies=True,
        session=None,
        error_handling=True,
        timeout=None,
        follow_redirects=None,
        use_basic_auth=True,
        use_proxy=True,
        debugging_id=None,
        new_connection=False,
        respect_size_limit=None,
        binary_response=False,
    ):
        """
        POST's data to a uri using a proxy, user agents, and other settings
        that where set previously.

        :param uri: This is the url where to post.
        :param data: A string with the data for the POST.
        :param debugging_id: A unique identifier for this call to audit()

        :see: The GET() for documentation on the other parameters
        :return: An HTTPResponse object.
        """
        req = self._request_builder.build_post(
            uri,
            data,
            headers,
            cookies,
            session,
            error_handling,
            timeout,
            use_basic_auth,
            use_proxy,
            debugging_id,
            new_connection,
            binary_response,
        )

        return self.send(req, grep=grep)

    def __getattr__(self, method_name):
        """
        This is a "catch-all" way to be able to handle every HTTP method.

        :param method_name: The name of the method being called:
        xurllib_instance.OPTIONS will make method_name == 'OPTIONS'.
        """

        def any_method(
            uri_opener,
            method,
            uri,
            data=None,
            headers=None,
            cache=False,
            grep=True,
            cookies=True,
            session=None,
            error_handling=True,
            timeout=None,
            use_basic_auth=True,
            use_proxy=True,
            follow_redirects=False,
            debugging_id=None,
            new_connection=False,
            respect_size_limit=None,
            binary_response=False,
        ):
            """
            :return: An HTTPResponse object that's the result of sending
                     the request with a method different from GET or POST.
            """
            req = uri_opener._request_builder.build_custom(
                method,
                uri,
                data,
                headers,
                cache,
                cookies,
                session,
                error_handling,
                timeout,
                use_basic_auth,
                use_proxy,
                follow_redirects,
                debugging_id,
                new_connection,
                binary_response,
            )
            return uri_opener.send(req, grep=grep)

        method_partial = functools.partial(any_method, self, method_name)
        method_partial.__doc__ = f"Send {method_name} HTTP request"
        return method_partial

    def _track_rtt(self, http_response, debugging_id):
        """
        Add the RTT associated with this response to the sum of all RTTs sent
        during this debugging_id.

        :param http_response: The HTTP response that is going out to the caller
        :param debugging_id: The debugging_id (if any) associated with the request
        :return: None
        """
        # HTTPErrors raised by the handlers don't measure the RTT
        if not hasattr(http_response, "get_wait_time"):
            return

        rtt = http_response.get_wait_time()
        rtt_sum = self._rtt_sum_debugging_id.get(debugging_id, default=None)
        if rtt_sum is None:
            self._rtt_sum_debugging_id[debugging_id] = rtt
        else:
            self._rtt_sum_debugging_id[debugging_id] = rtt_sum + rtt

    def get_rtt_for_debugging_id(self, debugging_id):
        if debugging_id is None:
            return

        return self._rtt_sum_debugging_id.get(debugging_id, default=None)

    def add_headers(self, req, headers=None):
        return self._request_preparer.add_headers(req, headers)

    def assert_allowed_proto(self, req):
        self._request_preparer.assert_allowed_proto(req)

    def send(self, req, grep=True):
        """
        Actually send the request object.

        :param req: The HTTPRequest object that represents the request.
        :param grep: Should grep the HTTP request / response
        :return: An HTTPResponse object.
        """
        # This is the place where pause and stop are implemented
        self._before_send_hook(req)

        # Sanitize the URL
        self.assert_allowed_proto(req)

        original_url = req._original_url
        original_url_inst = req._original_url_object
        req = self._evasion(req)
        req._original_url = original_url
        req._original_url_object = original_url_inst

        try:
            res = self._opener.open(req)
        except urllib.error.HTTPError as e:
            # Raised by the handlers, for example when NTLM authentication
            # fails. Those errors are raised before the cache handler numbers
            # the response
            if not hasattr(e, "id"):
                e.id = consecutive_number_generator.inc()

            return self._handle_send_success(
                req, e, grep, original_url, original_url_inst
            )

        except (
            OSError,
            URLTimeoutError,
            ConnectionPoolException,
            OpenSSL.SSL.Error,
            OpenSSL.SSL.SysCallError,
            OpenSSL.SSL.ZeroReturnError,
            BadStatusLine,
        ) as e:
            return self._handle_send_socket_error(req, e, grep, original_url)

        except (http.client.HTTPException, HTTPRequestException) as e:
            # URLError is an OSError and is handled above
            return self._handle_send_urllib_error(req, e, grep, original_url)

        else:
            return self._handle_send_success(
                req, res, grep, original_url, original_url_inst
            )

    def _handle_send_socket_error(self, req, exception, grep, original_url):
        return self._error_handler.handle_socket_error(
            req, exception, grep, original_url
        )

    def _handle_send_urllib_error(self, req, exception, grep, original_url):
        return self._error_handler.handle_urllib_error(
            req, exception, grep, original_url
        )

    def _generic_send_error_handler(self, req, exception, grep, original_url):
        return self._error_handler._handle_generic_error(
            req, exception, grep, original_url
        )

    def _handle_send_success(self, req, res, grep, original_url, original_url_inst):
        return self._response_success_handler.handle(
            req, res, grep, original_url, original_url_inst
        )

    def _retry(self, req, grep, url_error):
        return self._retry_handler.retry(req, grep, url_error)

    def _log_failed_response(self, request, exception, original_url):
        self._failed_response_recorder.record(request, exception, original_url)

    def _should_stop_scan(self, request):
        """Return whether consecutive failures indicate an unreachable server."""
        return self._response_history.should_stop_scan(
            lambda: self._server_root_path_is_reachable(request)
        )

    def _server_root_path_is_reachable(self, request):
        return self._reachability_checker.check(request)

    def get_error_rate(self):
        """
        :return: The error rate as an integer 0-100
        """
        return self._response_history.get_error_rate()

    def _log_error_rate(self):
        """
        Logs the error rate to the debug() log, useful to understand why a scan
        fails with "Too many consecutive errors"

        :see: https://github.com/andresriancho/w3af/issues/8698
        """
        error_rate = self.get_error_rate()
        LOGGER.debug(f"ExtendedUrllib error rate is at {int(error_rate)}%")

    def _handle_error_count_exceeded(self, error):
        """
        Handle the case where we exceeded MAX_ERROR_COUNT
        """
        # Create a detailed exception message
        msg = (
            "w3af found too many consecutive errors while performing"
            " HTTP requests. In most cases this means that the remote web"
            " server is not reachable anymore, the network is down, or"
            " a WAF is blocking our tests. The last exception message"
            ' was "%s" (%s.%s).'
        )

        reason_msg = get_exception_reason(error)
        args = (error, error.__class__.__module__, error.__class__.__name__)

        # If I got a reason, it means that it is a known exception.
        if reason_msg is not None:
            # Stop using ExtendedUrllib instance
            e = ScanMustStopByKnownReasonExc(msg % args, reason=reason_msg)

        else:
            last_errors = self._response_history.get_recent_messages(MAX_ERROR_COUNT)
            e = ScanMustStopByUnknownReasonExc(msg % args, errs=last_errors)

        LOGGER.debug(
            "The extended urllib will raise a scan must stop exception"
            " for each request after this message. The remote server is"
            " unreachable."
        )
        self._stop_exception = e

        raise self._stop_exception

    def _log_successful_response(self, response):
        host = response.get_url().get_domain()
        self._response_history.record_success(host, response.get_wait_time())

    def set_grep_queue_put(self, grep_queue_put):
        self._grep_dispatcher.set_callback(grep_queue_put)

    def set_evasion_plugins(self, evasion_plugins):
        self._evasion_pipeline.set_plugins(evasion_plugins)

    @property
    def _evasion_plugins(self):
        return self._evasion_pipeline.plugins

    def _evasion(self, request):
        return self._evasion_pipeline.apply(request)

    def _grep(self, request, response):
        self._grep_dispatcher.dispatch(request, response)


def raise_size_limit(respect_size_limit):
    return SizeLimitOverride(cf.cf).apply(respect_size_limit)
