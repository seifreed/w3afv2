"""Assemble the collaborators used by the HTTP request facade."""

import threading
from dataclasses import dataclass
from typing import Any

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
from w3af.core.data.url.request_mode_controller import RequestModeController
from w3af.core.data.url.request_preparer import RequestPreparer
from w3af.core.data.url.request_preflight import RequestPreflight
from w3af.core.data.url.request_retry_handler import RequestRetryHandler
from w3af.core.data.url.request_sender import RequestSender
from w3af.core.data.url.response_history import ResponseHistory
from w3af.core.data.url.response_success_handler import ResponseSuccessHandler
from w3af.core.data.url.scan_error_policy import ScanErrorPolicy
from w3af.core.data.url.scan_request_control import ScanRequestControl
from w3af.core.data.url.server_reachability_checker import ServerReachabilityChecker
from w3af.core.data.url.session_lifecycle import SessionLifecycle
from w3af.core.data.url.size_limit_override import SizeLimitOverride
from w3af.core.data.url.timeout_adjustment_policy import TimeoutAdjustmentPolicy
from w3af.core.data.url.timeout_manager import TimeoutManager
from w3af.core.data.url.worker_pool_adjuster import WorkerPoolAdjuster


@dataclass(frozen=True)
class RequestComponents:
    """Collaborators assembled for one ``ExtendedUrllib`` instance."""

    average_rtt_mutant: GetAverageRTTForMutant
    response_history: ResponseHistory
    count_lock: Any
    rate_limiter: RateLimiter
    timeout_manager: TimeoutManager
    request_mode_controller: RequestModeController
    size_limit_override: SizeLimitOverride
    timeout_adjustment: TimeoutAdjustmentPolicy
    request_metrics: RequestMetrics
    worker_pool_adjuster: WorkerPoolAdjuster
    error_pause_controller: HttpErrorPauseController
    grep_dispatcher: GrepDispatcher
    evasion_pipeline: RequestEvasionPipeline
    request_preparer: RequestPreparer
    request_builder: RequestBuilder
    response_success_handler: ResponseSuccessHandler
    retry_handler: RequestRetryHandler
    reachability_checker: ServerReachabilityChecker
    request_control: ScanRequestControl
    request_preflight: RequestPreflight
    scan_error_policy: ScanErrorPolicy
    failed_response_recorder: FailedResponseRecorder
    error_handler: RequestErrorHandler
    session_lifecycle: SessionLifecycle
    request_sender: RequestSender
    request_api: RequestApi


class RequestComponentFactory:
    """Build the request pipeline around an existing opener facade."""

    def __init__(
        self,
        opener: Any,
        settings: Any,
        configuration: Any,
        sleep: Any,
        parser_cache: Any,
        id_generator: Any,
        log_debug: Any,
        log_error: Any,
    ) -> None:
        self._opener = opener
        self._settings = settings
        self._configuration = configuration
        self._sleep = sleep
        self._parser_cache = parser_cache
        self._id_generator = id_generator
        self._log_debug = log_debug
        self._log_error = log_error

    def create(self) -> RequestComponents:
        average_rtt_mutant = GetAverageRTTForMutant(self._opener)
        response_history = ResponseHistory()
        count_lock = threading.RLock()
        rate_limiter = RateLimiter(self._settings, self._sleep)
        timeout_manager = TimeoutManager(self._settings)
        request_mode_controller = RequestModeController(
            self._opener.clear_timeout,
            self._settings.close_connections,
        )
        size_limit_override = SizeLimitOverride(self._configuration)
        request_metrics = RequestMetrics()
        worker_pool_adjuster = WorkerPoolAdjuster(
            self._opener.get_error_rate,
            self._log_debug,
        )
        error_pause_controller = HttpErrorPauseController(
            self._opener.get_error_rate,
            self._opener.get_total_requests,
            self._sleep,
            self._log_debug,
        )
        grep_dispatcher = GrepDispatcher()
        evasion_pipeline = RequestEvasionPipeline(self._log_error)
        request_preparer = RequestPreparer(self._settings)
        request_builder = RequestBuilder(
            lambda: self._settings,
            self._opener.setup,
            self._opener.get_timeout,
            self._opener.add_headers,
        )
        timeout_adjustment = TimeoutAdjustmentPolicy(
            timeout_manager,
            self._opener.get_average_rtt,
            self._opener.get_total_requests,
            self._opener.set_timeout,
            self._opener.get_timeout,
            self._log_debug,
        )
        response_success_handler = ResponseSuccessHandler(
            self._log_debug,
            self._opener._log_successful_response,
            self._opener._track_rtt,
            worker_pool_adjuster.adjust,
            self._opener._grep,
            self._parser_cache,
        )
        retry_handler = RequestRetryHandler(
            self._opener.send,
            self._opener.get_timeout,
            self._log_debug,
        )
        reachability_checker = ServerReachabilityChecker(
            self._opener.get_timeout,
            self._opener.set_timeout,
            self._opener.add_headers,
            self._opener.send,
            self._log_debug,
        )
        request_control = ScanRequestControl()
        request_preflight = RequestPreflight(
            request_control,
            error_pause_controller,
            rate_limiter,
            timeout_adjustment,
            request_metrics,
        )
        scan_error_policy = ScanErrorPolicy(
            response_history,
            reachability_checker,
            request_control,
            self._log_debug,
        )
        failed_response_recorder = FailedResponseRecorder(
            response_history,
            self._opener.get_timeout,
            self._opener._log_error_rate,
            self._log_debug,
        )
        error_handler = RequestErrorHandler(
            self._log_debug,
            self._opener._increase_timeout_on_error,
            count_lock,
            self._opener._log_failed_response,
            self._opener._should_stop_scan,
            self._opener._handle_error_count_exceeded,
            worker_pool_adjuster.adjust,
            self._opener._retry,
        )
        session_lifecycle = SessionLifecycle(
            lambda: self._settings,
            request_control,
            response_history,
            self._opener._reset_total_requests,
            lambda: request_mode_controller.set_exploit_mode(False),
            self._opener.clear_timeout,
            request_metrics.clear_rtt,
        )
        request_sender = RequestSender(
            lambda request: self._opener._before_send_hook(request),
            self._opener.assert_allowed_proto,
            lambda: self._opener._opener,
            self._opener._evasion,
            self._id_generator,
            self._opener._handle_send_socket_error,
            self._opener._handle_send_urllib_error,
            self._opener._handle_send_success,
        )
        request_api = RequestApi(
            request_builder,
            size_limit_override,
            self._opener.send,
        )

        return RequestComponents(
            average_rtt_mutant,
            response_history,
            count_lock,
            rate_limiter,
            timeout_manager,
            request_mode_controller,
            size_limit_override,
            timeout_adjustment,
            request_metrics,
            worker_pool_adjuster,
            error_pause_controller,
            grep_dispatcher,
            evasion_pipeline,
            request_preparer,
            request_builder,
            response_success_handler,
            retry_handler,
            reachability_checker,
            request_control,
            request_preflight,
            scan_error_policy,
            failed_response_recorder,
            error_handler,
            session_lifecycle,
            request_sender,
            request_api,
        )
