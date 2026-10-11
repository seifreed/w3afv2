"""
status.py

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

import time

from w3af.core.controllers.core_helpers.status_adjustments import (
    get_audit_adjustment,
    get_crawl_adjustment,
    get_grep_adjustment,
)
from w3af.core.controllers.core_helpers.status_consumers import ConsumerMetrics
from w3af.core.controllers.core_helpers.status_eta import (
    AUDIT,
    CRAWL,
    GREP,
    Adjustment,
    EtaCalculator,
)
from w3af.core.controllers.core_helpers.status_lifecycle import StatusLifecycle
from w3af.core.controllers.core_helpers.status_presenter import StatusPresenter
from w3af.core.controllers.misc.epoch_to_string import epoch_to_string
from w3af.core.data.misc.number_generator import NumberGenerator

PAUSED = "Paused"
STOPPED = "Stopped"
RUNNING = "Running"


class CoreStatus:
    """
    This class maintains the status of the w3afCore. During scan the different
    phases of the process will change the status (set) and the UI will be
    calling the different methods to (get) the information required.
    """

    def __init__(
        self, output, consumer_metrics=None, scans_completed=0, id_generator=None
    ):
        self._output = output
        self._id_generator = NumberGenerator() if id_generator is None else id_generator
        self._consumer_metrics = consumer_metrics or ConsumerMetrics()
        self._lifecycle = StatusLifecycle(scans_completed)
        self._request_count_at_start = self._id_generator.get()

        # Init some internal values
        # This indicates the plugin that is running right now for each
        # plugin_type
        self._running_plugin = {}
        self._latest_ptype, self._latest_pname = None, None

        # The current fuzzable request that the core is analyzing at each phase
        # where a phase means crawl/audit
        self._current_fuzzable_request = {}

        self._eta_calculator = EtaCalculator()

    def detach_runtime_dependencies(self):
        self._consumer_metrics = ConsumerMetrics()

    def set_output(self, output):
        self._output = output

    @property
    def scans_completed(self):
        return self._lifecycle.scans_completed

    @scans_completed.setter
    def scans_completed(self, value):
        self._lifecycle.scans_completed = value

    def pause(self, pause_yes_no):
        self._lifecycle.pause(pause_yes_no)
        self._output.debug("The user paused / unpaused the scan.")

    def start(self):
        self._lifecycle.start()

    def stop(self):
        # Now I'm definitely not running:
        self._lifecycle.stop()

    def get_status(self):
        """
        :return: A string representing the current w3af core status.
        """
        if self.is_paused():
            return PAUSED

        elif not self.is_running():
            return STOPPED

        else:
            crawl_plugin = self.get_running_plugin("crawl")
            audit_plugin = self.get_running_plugin("audit")

            crawl_fr = self.get_current_fuzzable_request("crawl")
            audit_fr = self.get_current_fuzzable_request("audit")

            if (
                crawl_plugin is None
                and audit_plugin is None
                and crawl_fr is None
                and audit_fr is None
            ):
                return "Starting scan."

            status_str = ""
            if crawl_plugin is not None and crawl_fr is not None:
                status_str += "Crawling %s using %s.%s"
                status_str %= (crawl_fr, "crawl", crawl_plugin)

            if audit_plugin is not None and audit_fr is not None:
                if status_str:
                    status_str += "\n"

                status_str += f"Auditing {audit_fr} using audit.{audit_plugin}"

            status_str = status_str.replace("\x00", "")
            return status_str

    def set_running_plugin(self, plugin_type, plugin_name, log=True):
        """
        This method saves the phase and plugin name in order to be shown
        to the user.

        :param plugin_name: The plugin_type which the w3afCore is running
        :param plugin_name: The plugin_name which the w3afCore is running
        """
        self._running_plugin[plugin_type] = plugin_name
        self._latest_ptype, self._latest_pname = plugin_type, plugin_name

    def get_running_plugin(self, plugin_type):
        """
        :return: The plugin that the core is running when the method is called.
        """
        return self._running_plugin.get(plugin_type, None)

    def latest_running_plugin(self):
        """
        :return: Tuple with plugin_type and plugin_name for the latest running
                 plugin reported using set_running_plugin.
        """
        return self._latest_ptype, self._latest_pname

    def is_running(self):
        """
        :return: If the user has called start, and then wants to know if the
        core is still working, it should call is_running() to know that.
        """
        return self._lifecycle.is_running()

    def is_paused(self):
        return self._lifecycle.is_paused()

    def has_started(self):
        """
        :return: True once start() was called, the run time, ETA and progress
                 can only be calculated after that
        """
        return self._lifecycle.has_started()

    def get_run_time(self):
        """
        :return: The time (in minutes) between now and the call to start().
        """
        return self._lifecycle.get_run_time()

    def get_run_time_seconds(self):
        """
        :return: The time (in seconds) between now and the call to start().
        """
        return self._lifecycle.get_run_time_seconds()

    def get_scan_time(self):
        """
        :return: The scan time in a format similar to: "3h 25m 32s"
        """
        return self._lifecycle.get_scan_time()

    def get_rpm(self):
        """
        :return: The number of HTTP requests per minute performed since the
                 start of the scan.
        """
        return int(self.get_sent_request_count() / self.get_run_time())

    def scan_finished(self):
        self._lifecycle.scan_finished()
        self._running_plugin = {}
        self._current_fuzzable_request = {}

    def get_current_fuzzable_request(self, plugin_type):
        """
        :return: The current fuzzable request that the w3afCore is working on.
        """
        return self._current_fuzzable_request.get(plugin_type, None)

    def set_current_fuzzable_request(self, plugin_type, fuzzable_request):
        """
        :param fuzzable_request: The FuzzableRequest that the w3afCore is
        working on right now.
        """
        self._current_fuzzable_request[plugin_type] = fuzzable_request

    def get_crawl_input_speed(self):
        return self._consumer_metrics.get_input_speed(CRAWL)

    def get_crawl_output_speed(self):
        return self._consumer_metrics.get_output_speed(CRAWL)

    def get_crawl_qsize(self):
        return self._consumer_metrics.get_queue_size(CRAWL)

    def get_crawl_output_qsize(self):
        return self._consumer_metrics.get_output_queue_size(CRAWL)

    def get_crawl_processed_tasks(self):
        return self._consumer_metrics.get_processed_tasks(CRAWL)

    def has_finished_crawl(self):
        return self._consumer_metrics.has_finished(CRAWL)

    def get_crawl_eta(self):
        if not self.has_started():
            return None

        adjustment = self.get_crawl_adjustment_ratio()

        return self.calculate_eta(
            self.get_crawl_input_speed(),
            self.get_crawl_output_speed(),
            self.get_crawl_qsize(),
            CRAWL,
            adjustment=adjustment,
        )

    def get_grep_processed_tasks(self):
        return self._consumer_metrics.get_processed_tasks(GREP)

    def get_grep_qsize(self):
        return self._consumer_metrics.get_queue_size(GREP)

    def has_finished_grep(self):
        return self._consumer_metrics.has_finished(GREP)

    def get_grep_input_speed(self):
        return self._consumer_metrics.get_input_speed(GREP)

    def get_grep_output_speed(self):
        return self._consumer_metrics.get_output_speed(GREP)

    def get_grep_eta(self):
        if not self.has_started():
            return None

        adjustment = self.get_grep_adjustment_ratio()

        return self.calculate_eta(
            self.get_grep_input_speed(),
            self.get_grep_output_speed(),
            self.get_grep_qsize(),
            GREP,
            adjustment=adjustment,
        )

    def get_audit_input_speed(self):
        return self._consumer_metrics.get_input_speed(AUDIT)

    def get_audit_output_speed(self):
        return self._consumer_metrics.get_output_speed(AUDIT)

    def get_audit_qsize(self):
        return self._consumer_metrics.get_queue_size(AUDIT)

    def get_audit_processed_tasks(self):
        return self._consumer_metrics.get_processed_tasks(AUDIT)

    def has_finished_audit(self):
        return self._consumer_metrics.has_finished(AUDIT)

    def get_audit_eta(self):
        if not self.has_started():
            return None

        adjustment = self.get_audit_adjustment_ratio()

        return self.calculate_eta(
            self.get_audit_input_speed(),
            self.get_audit_output_speed(),
            self.get_audit_qsize(),
            AUDIT,
            adjustment=adjustment,
        )

    def get_core_worker_pool_queue_size(self):
        return self._consumer_metrics.get_worker_pool_queue_size()

    def log_calculate_eta(
        self, eta, input_speed, output_speed, queue_size, _type, adjustment
    ):
        """
        :return: None, a log line is added.
        """
        run_time = self.get_run_time_seconds()

        msg = (
            "Calculated %s ETA: %.2f seconds. (input speed:%.2f,"
            " output speed:%.2f, queue size: %i, adjustment known: %.2f,"
            " adjustment unknown: %.2f, average: %s, run time: %.2f)"
        )
        args = (
            _type,
            eta,
            input_speed,
            output_speed,
            queue_size,
            adjustment.known,
            adjustment.unknown,
            adjustment.average,
            run_time,
        )

        self._output.debug(msg % args)

    def calculate_eta(
        self, input_speed, output_speed, queue_size, _type, adjustment=None
    ):
        """
        Do our best effort to calculate the ETA for a specific queue
        for which we have the input speed, output speed and current
        size.

        :param input_speed: The speed at which items are added to the queue
        :param output_speed: The speed at which items are read from the queue
        :param queue_size: The current queue size
        :param _type: The type of ETA we're calculating
        :param adjustment: Adjustment instance which indicates how to adjust the
                           ETA for this calculation. The adjustment data is just
                           two ratios which multiply the result. There is one
                           ratio for the case where input speed > output speed
                           and another for the case where output speed > input
                           speed.
        :return: ETA in epoch format, None if one of the parameters is None.
        """
        if adjustment is None:
            adjustment = Adjustment()

        eta = self._eta_calculator.calculate(
            input_speed, output_speed, queue_size, _type, adjustment
        )

        self.log_calculate_eta(
            eta, input_speed, output_speed, queue_size, _type, adjustment
        )

        return eta

    def get_simplified_status(self):
        """
        :return: The status as a very simple string
        """
        if self.is_paused():
            return PAUSED

        elif not self.is_running():
            return STOPPED

        return RUNNING

    def epoch_eta_to_string(self, eta):
        if eta is None:
            return None

        return epoch_to_string(time.time() - eta)

    def get_status_as_dict(self):
        return StatusPresenter(self).as_dict()

    def get_progress_percentage(self, eta=None):
        """
        :return: A % of scan progress as an integer
        """
        eta = self.get_eta() if eta is None else eta

        run_time = self.get_run_time_seconds()
        estimated_end_time = run_time + eta

        progress = int(run_time / estimated_end_time * 100)

        # If the calculated progress is 100% but any of the consumers is still
        # running, then we should return 99%. This happens when the ETA estimation
        # is incorrect (often)
        if progress == 100 and self.any_consumer_running():
            progress = 99

        self._output.debug(
            f"The scan will finish in {eta:.2f} seconds ({progress}% done)"
        )

        return progress

    def any_consumer_running(self):
        if not self.has_finished_crawl():
            return True

        if not self.has_finished_audit():
            return True

        return not self.has_finished_grep()

    def get_crawl_adjustment_ratio(self):
        """
        During the first minutes of the scan the ETA calculations are usually
        very inaccurate, indicating the the scan will finish way sooner than
        reality.

        In order to fix this issue provide a set of specific adjustment
        ratios for the ETA calculation (see how these are used in calculate_eta)
        which should be used during the first minutes of the scan.

        Also provide specific adjustment ratios for different scan phases, such
        as "crawl, audit and grep running", "crawl finished, audit and grep running",
        etc.

        :return: The crawl adjustment ratio to use in this run
        """
        return get_crawl_adjustment(self.get_run_time_seconds())

    def get_audit_adjustment_ratio(self):
        """
        :see: Documentation for get_crawl_adjustment_ratio
        """
        return get_audit_adjustment(
            self.get_run_time_seconds(), self.has_finished_crawl()
        )

    def get_grep_adjustment_ratio(self):
        """
        :see: Documentation for get_crawl_adjustment_ratio
        """
        return get_grep_adjustment(
            self.get_run_time_seconds(),
            self.has_finished_crawl(),
            self.has_finished_audit(),
        )

    def log_eta(self, msg):
        self._output.debug(f"[get_eta] {msg}")

    def get_eta(self):
        """
        Calculate the estimated number of seconds to complete the scan
        :return: Scan ETA in seconds.
        """
        # We're most likely never going to reach this case, but just in case
        # I'm adding it. Just zero, meaning: we're finishing now
        if self.has_finished_grep():
            self.log_eta("ETA is 0. Grep consumer has already finished.")
            return 0

        # The easiest case is when we're not sending any more HTTP requests,
        # we just need to run the grep plugins (if enabled) on the HTTP requests
        # and responses that were captured before
        if self.has_finished_crawl() and self.has_finished_audit():
            self.log_eta(
                "Crawl and audit consumers have finished,"
                " ETA calculated using grep ETA."
            )
            return self.get_grep_eta()

        # The crawling phase has finished, but we're running audit (if enabled)
        # and grep (if enabled). Grep and audit plugins will run in different
        # threads. In most cases audit plugins will finish and grep plugins
        # will continue to run for (at least) a couple of minutes.
        if self.has_finished_crawl() and not self.has_finished_audit():
            grep_eta = self.get_grep_eta()
            audit_eta = self.get_audit_eta()

            after_audit = 0.0
            if grep_eta >= audit_eta:
                after_audit = grep_eta - audit_eta
                after_audit = after_audit * 0.1

            self.log_eta(
                "Crawl has finished. Using audit and grep ETAs"
                " to calculate overall ETA."
            )
            return audit_eta + after_audit

        # The crawling, audit and grep (all if they were enabled) are running.
        # Estimating ETA here is difficult!
        self.log_eta("ETA calculation will merge ETAs for all phases.")

        grep_eta = self.get_grep_eta()
        audit_eta = self.get_audit_eta()
        crawl_eta = self.get_crawl_eta()

        audit_after_crawl = 0.0
        if audit_eta > crawl_eta:
            audit_after_crawl = audit_eta - crawl_eta

        grep_after_crawl_audit = 0.0
        if grep_eta >= audit_eta:
            grep_after_crawl_audit += grep_eta - audit_eta

        if grep_eta >= crawl_eta:
            grep_after_crawl_audit += grep_eta - crawl_eta

        audit_after_crawl = audit_after_crawl * 0.75
        grep_after_crawl_audit = grep_after_crawl_audit * 0.05
        return crawl_eta + audit_after_crawl + grep_after_crawl_audit

    def get_sent_request_count(self):
        """
        :return: The number of HTTP requests that have been sent
        """
        return self._id_generator.get() - self._request_count_at_start

    def get_long_status(self):
        return StatusPresenter(self).long_status()
