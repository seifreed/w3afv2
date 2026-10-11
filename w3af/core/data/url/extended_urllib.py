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

import logging
import threading
import time
import uuid

from w3af.core.data.kb.config import Config
from w3af.core.data.misc.number_generator import NumberGenerator
from w3af.core.data.url.constants import TIMEOUT_ADJUST_LIMIT
from w3af.core.data.url.failed_response_recorder import FailedResponseRecorder
from w3af.core.data.url.get_average_rtt import GetAverageRTTForMutant
from w3af.core.data.url.grep_dispatcher import GrepDispatcher
from w3af.core.data.url.http_error_pause_controller import HttpErrorPauseController
from w3af.core.data.url.rate_limiter import RateLimiter
from w3af.core.data.url.request_builder import RequestBuilder
from w3af.core.data.url.request_error_handler import RequestErrorHandler
from w3af.core.data.url.request_evasion import RequestEvasionPipeline
from w3af.core.data.url.request_api import RequestApi
from w3af.core.data.url.request_metrics import RequestMetrics
from w3af.core.data.url.request_preparer import RequestPreparer
from w3af.core.data.url.request_preflight import RequestPreflight
from w3af.core.data.url.request_retry_handler import RequestRetryHandler
from w3af.core.data.url.request_sender import RequestSender
from w3af.core.data.url.response_history import ResponseHistory
from w3af.core.data.url.response_success_handler import ResponseSuccessHandler
from w3af.core.data.url.scan_request_control import ScanRequestControl
from w3af.core.data.url.scan_error_policy import ScanErrorPolicy
from w3af.core.data.url.server_reachability_checker import ServerReachabilityChecker
from w3af.core.data.url.session_lifecycle import SessionLifecycle
from w3af.core.data.url.size_limit_override import SizeLimitOverride
from w3af.core.data.url.timeout_adjustment_policy import TimeoutAdjustmentPolicy
from w3af.core.data.url.timeout_manager import TimeoutManager
from w3af.core.data.url.worker_pool_adjuster import WorkerPoolAdjuster
from w3af.core.exceptions import ScanMustStopException

from . import opener_settings

LOGGER = logging.getLogger(__name__)


class ExtendedUrllib:
    """
    This is a urllib2 wrapper.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    def __init__(
        self,
        http_log_callback=None,
        sleep=time.sleep,
        configuration=None,
        resolver=None,
        parser_cache=None,
        id_generator=None,
        db=None,
    ):
        self._configuration = Config() if configuration is None else configuration
        self._id_generator = NumberGenerator() if id_generator is None else id_generator
        self.settings = opener_settings.OpenerSettings(
            http_log_callback,
            configuration=self._configuration,
            resolver=resolver,
            id_generator=self._id_generator,
            db=db,
        )
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
        self._size_limit_override = SizeLimitOverride(self._configuration)
        self._timeout_adjustment = TimeoutAdjustmentPolicy(
            self._timeout_manager,
            self.get_average_rtt,
            self.get_total_requests,
            self.set_timeout,
            self.get_timeout,
            LOGGER.debug,
        )

        self._request_metrics = RequestMetrics()

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
            parser_cache,
        )
        self._retry_handler = RequestRetryHandler(
            self.send,
            self.get_timeout,
            LOGGER.debug,
        )
        self._reachability_checker = ServerReachabilityChecker(
            self.get_timeout,
            self.set_timeout,
            self.add_headers,
            self.send,
            LOGGER.debug,
        )
        self._request_control = ScanRequestControl()
        self._request_preflight = RequestPreflight(
            self._request_control,
            self._error_pause_controller,
            self._rate_limiter,
            self._timeout_adjustment,
            self._request_metrics,
        )
        self._scan_error_policy = ScanErrorPolicy(
            self._response_history,
            self._reachability_checker,
            self._request_control,
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
        self._session_lifecycle = SessionLifecycle(
            lambda: self.settings,
            self._request_control,
            self._response_history,
            self._reset_total_requests,
            lambda: self.set_exploit_mode(False),
            self.clear_timeout,
            self._request_metrics.clear_rtt,
        )
        self._request_sender = RequestSender(
            self._before_send_hook,
            self.assert_allowed_proto,
            lambda: self._opener,
            self._evasion,
            self._id_generator,
            self._handle_send_socket_error,
            self._handle_send_urllib_error,
            self._handle_send_success,
        )
        self._request_api = RequestApi(
            self._request_builder,
            self._size_limit_override,
            self.send,
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
    def _stop_exception(self) -> ScanMustStopException | None:
        return self._request_control.stop_exception

    @_stop_exception.setter
    def _stop_exception(self, exception: ScanMustStopException | None) -> None:
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
        self._request_preflight.prepare(request, self.exploit_mode)

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
        return self._request_metrics.get_total_requests()

    @property
    def _sleep_log(self):
        return self._error_pause_controller.sleep_log

    def clear(self):
        self._session_lifecycle.clear()

    def end(self):
        self._session_lifecycle.end()

    def restart(self):
        self._session_lifecycle.restart()

    def setup(self):
        self._session_lifecycle.setup()

    def _reset_total_requests(self):
        self._request_metrics.reset_total_requests()

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
        return self._request_api.send_clean(mutant, debugging_id, grep)

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
        return self._request_api.send_raw_request(head, postdata)

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
        return self._request_api.send_mutant(
            mutant,
            callback=callback,
            grep=grep,
            cache=cache,
            cookies=cookies,
            session=session,
            error_handling=error_handling,
            timeout=timeout,
            follow_redirects=follow_redirects,
            use_basic_auth=use_basic_auth,
            respect_size_limit=respect_size_limit,
            debugging_id=debugging_id,
            binary_response=binary_response,
        )

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
        return self._request_api.GET(
            uri,
            data=data,
            headers=headers,
            cache=cache,
            grep=grep,
            cookies=cookies,
            session=session,
            respect_size_limit=respect_size_limit,
            new_connection=new_connection,
            error_handling=error_handling,
            timeout=timeout,
            follow_redirects=follow_redirects,
            use_basic_auth=use_basic_auth,
            use_proxy=use_proxy,
            debugging_id=debugging_id,
            binary_response=binary_response,
        )

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
        return self._request_api.POST(
            uri,
            data=data,
            headers=headers,
            grep=grep,
            cache=cache,
            cookies=cookies,
            session=session,
            error_handling=error_handling,
            timeout=timeout,
            follow_redirects=follow_redirects,
            use_basic_auth=use_basic_auth,
            use_proxy=use_proxy,
            debugging_id=debugging_id,
            new_connection=new_connection,
            respect_size_limit=respect_size_limit,
            binary_response=binary_response,
        )

    def __getattr__(self, method_name):
        return getattr(self._request_api, method_name)

    def _track_rtt(self, http_response, debugging_id):
        """
        Add the RTT associated with this response to the sum of all RTTs sent
        during this debugging_id.

        :param http_response: The HTTP response that is going out to the caller
        :param debugging_id: The debugging_id (if any) associated with the request
        :return: None
        """
        # HTTPErrors raised by the handlers don't measure the RTT
        self._request_metrics.track_rtt(http_response, debugging_id)

    def get_rtt_for_debugging_id(self, debugging_id):
        return self._request_metrics.get_rtt(debugging_id)

    def add_headers(self, req, headers=None):
        return self._request_preparer.add_headers(req, headers)

    def assert_allowed_proto(self, req):
        self._request_preparer.assert_allowed_proto(req)

    def send(self, req, grep=True):
        """Actually send the request through the transport boundary."""
        return self._request_sender.send(req, grep)

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
        return self._scan_error_policy.should_stop_scan(request)

    def _server_root_path_is_reachable(self, request):
        return self._scan_error_policy.server_root_path_is_reachable(request)

    def get_error_rate(self):
        """
        :return: The error rate as an integer 0-100
        """
        return self._scan_error_policy.get_error_rate()

    def _log_error_rate(self):
        """
        Logs the error rate to the debug() log, useful to understand why a scan
        fails with "Too many consecutive errors"

        :see: https://github.com/andresriancho/w3af/issues/8698
        """
        self._scan_error_policy.log_error_rate()

    def _handle_error_count_exceeded(self, error):
        """
        Handle the case where we exceeded MAX_ERROR_COUNT
        """
        self._scan_error_policy.handle_error_count_exceeded(error)

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
