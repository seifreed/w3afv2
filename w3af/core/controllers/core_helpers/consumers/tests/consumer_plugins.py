"""
consumer_plugins.py

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

Small plugins with a well known behaviour which the consumer tests run in
order to reach every branch of the consumers.
"""

import queue
import threading
import time

from w3af.core.controllers.core_helpers.exception_handler import ExceptionData
from w3af.core.controllers.core_helpers.strategy_observers.strategy_observer import (
    StrategyObserver,
)
from w3af.core.controllers.plugins.audit_plugin import AuditPlugin
from w3af.core.controllers.plugins.auth_plugin import AuthPlugin
from w3af.core.controllers.plugins.bruteforce_plugin import BruteforcePlugin
from w3af.core.controllers.plugins.crawl_plugin import CrawlPlugin
from w3af.core.controllers.plugins.grep_plugin import GrepPlugin
from w3af.core.exceptions import BaseFrameworkException, RunOnce, ScanMustStopException

WAIT_TIMEOUT = 10


def wait_until(condition):
    deadline = time.time() + WAIT_TIMEOUT
    while not condition():
        if time.time() > deadline:
            raise AssertionError("Timed out waiting for the condition")
        time.sleep(0.01)


class EndBehaviour:
    """
    Plugins with this mixin raise end_error (if any) when end() is called
    """

    end_error: Exception | None = None

    def end(self):
        self.end_calls = getattr(self, "end_calls", 0) + 1
        if self.end_error is not None:
            raise self.end_error


class recording_audit(EndBehaviour, AuditPlugin):
    def __init__(self):
        super().__init__()
        self.audited = []

    def audit(self, freq, orig_resp, debugging_id):
        self.audited.append((freq.get_uri().url_string, orig_resp.get_code()))


class crashing_audit(EndBehaviour, AuditPlugin):
    end_error = ValueError("audit end failed")

    def audit(self, freq, orig_resp, debugging_id):
        raise ValueError("audit failed")


class stopping_audit(EndBehaviour, AuditPlugin):
    end_error = ScanMustStopException("stop")


class counting_auth(EndBehaviour, AuthPlugin):
    def __init__(self, active_session=False):
        super().__init__()
        self.active_session = active_session
        self.logins = 0
        self.login_event = threading.Event()

    def has_active_session(self, debugging_id=None):
        return self.active_session

    def login(self, debugging_id=None):
        self.logins += 1
        self.login_event.set()


class crashing_auth(EndBehaviour, AuthPlugin):
    def has_active_session(self, debugging_id=None):
        raise ValueError("session check failed")


class recording_bruteforce(EndBehaviour, BruteforcePlugin):
    def __init__(self, found=()):
        super().__init__()
        self.found = list(found)
        self.bruteforced = []

    def bruteforce_wrapper(self, fuzzable_request):
        self.bruteforced.append(fuzzable_request)
        return self.found


class crashing_bruteforce(recording_bruteforce):
    end_error = ValueError("bruteforce end failed")

    def bruteforce_wrapper(self, fuzzable_request):
        raise ValueError("bruteforce failed")


class stopping_bruteforce(recording_bruteforce):
    end_error = ScanMustStopException("stop")


class queueing_crawl(EndBehaviour, CrawlPlugin):
    """
    Puts the configured items in the output queue the first time crawl() is
    called.
    """

    def __init__(self, items=()):
        super().__init__()
        self.items = list(items)
        self.crawled = []

    def crawl(self, fuzzable_request, debugging_id):
        self.crawled.append(fuzzable_request.get_uri().url_string)
        for item in self.items:
            self.output_queue.put(item)
        self.items = []


class failing_crawl(EndBehaviour, CrawlPlugin):
    """
    Raises crawl_error from crawl() and optionally returns a value instead of
    None, which breaks the plugin API.
    """

    crawl_error: Exception | None = None
    crawl_result: tuple | None = None

    def crawl(self, fuzzable_request, debugging_id):
        if self.crawl_error is not None:
            raise self.crawl_error
        return self.crawl_result


class framework_error_crawl(failing_crawl):
    crawl_error = BaseFrameworkException("crawl framework error")


class crashing_crawl(failing_crawl):
    crawl_error = ValueError("crawl failed")
    end_error = ValueError("crawl end failed")


class stopping_crawl(failing_crawl):
    end_error = ScanMustStopException("stop")


class run_once_crawl(failing_crawl):
    crawl_error = RunOnce()

    def get_type(self):
        return "infrastructure"


class list_returning_crawl(failing_crawl):
    crawl_result = ()


class recording_grep(EndBehaviour, GrepPlugin):
    def __init__(self):
        super().__init__()
        self.grepped = []

    def grep(self, fuzzable_request, response):
        self.grepped.append(response.get_uri().url_string)


class crashing_grep(EndBehaviour, GrepPlugin):
    end_error = ValueError("grep end failed")

    def grep(self, fuzzable_request, response):
        raise ValueError("grep failed")


class CrashingObserver(StrategyObserver):
    def crawl(self, craw_consumer, fuzzable_request):
        raise ValueError("crawl observer failed")

    def audit(self, audit_consumer, fuzzable_request):
        raise ValueError("audit observer failed")

    def bruteforce(self, bruteforce_consumer, fuzzable_request):
        raise ValueError("bruteforce observer failed")

    def grep(self, grep_consumer, request, response):
        raise ValueError("grep observer failed")


def drain_results(consumer):
    """
    :return: Every item in the consumer output queue
    """
    results = []
    while True:
        try:
            results.append(consumer.out_queue.get_nowait())
        except queue.Empty:
            return results


def reported_errors(consumer):
    """
    :return: (plugin, exception message) for each ExceptionData in the
             consumer output queue
    """
    return [
        (result.plugin, str(result.exception))
        for result in drain_results(consumer)
        if isinstance(result, ExceptionData)
    ]


def prepare_plugins(plugins, w3af_core):
    for plugin in plugins:
        plugin.set_url_opener(w3af_core.uri_opener)
        plugin.set_worker_pool(w3af_core.worker_pool)
    return plugins
