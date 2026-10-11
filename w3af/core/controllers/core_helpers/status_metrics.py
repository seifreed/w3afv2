"""Calculate scan progress from consumer and worker-pool metrics."""

from typing import Any

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


class StatusMetrics:
    """Expose consumer metrics and ETA calculations for a scan status."""

    def __init__(
        self,
        consumer_metrics: ConsumerMetrics,
        lifecycle: StatusLifecycle,
        output: Any,
    ):
        self._consumer_metrics = consumer_metrics
        self._lifecycle = lifecycle
        self._output = output
        self._eta_calculator = EtaCalculator()

    def detach_runtime_dependencies(self):
        self._consumer_metrics = ConsumerMetrics()

    def set_output(self, output):
        self._output = output

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
        if not self._lifecycle.has_started():
            return None

        return self.calculate_eta(
            self.get_crawl_input_speed(),
            self.get_crawl_output_speed(),
            self.get_crawl_qsize(),
            CRAWL,
            adjustment=self.get_crawl_adjustment_ratio(),
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
        if not self._lifecycle.has_started():
            return None

        return self.calculate_eta(
            self.get_grep_input_speed(),
            self.get_grep_output_speed(),
            self.get_grep_qsize(),
            GREP,
            adjustment=self.get_grep_adjustment_ratio(),
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
        if not self._lifecycle.has_started():
            return None

        return self.calculate_eta(
            self.get_audit_input_speed(),
            self.get_audit_output_speed(),
            self.get_audit_qsize(),
            AUDIT,
            adjustment=self.get_audit_adjustment_ratio(),
        )

    def get_core_worker_pool_queue_size(self):
        return self._consumer_metrics.get_worker_pool_queue_size()

    def log_calculate_eta(
        self, eta, input_speed, output_speed, queue_size, _type, adjustment
    ):
        """Log the inputs used to calculate an ETA."""
        run_time = self._lifecycle.get_run_time_seconds()
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
        """Calculate an ETA for one consumer queue."""
        if adjustment is None:
            adjustment = Adjustment()

        eta = self._eta_calculator.calculate(
            input_speed, output_speed, queue_size, _type, adjustment
        )
        self.log_calculate_eta(
            eta, input_speed, output_speed, queue_size, _type, adjustment
        )
        return eta

    def get_progress_percentage(self, eta=None):
        """Return the estimated scan progress as an integer percentage."""
        eta = self.get_eta() if eta is None else eta
        run_time = self._lifecycle.get_run_time_seconds()
        estimated_end_time = run_time + eta
        progress = int(run_time / estimated_end_time * 100)

        if progress == 100 and self.any_consumer_running():
            progress = 99

        self._output.debug(
            f"The scan will finish in {eta:.2f} seconds ({progress}% done)"
        )
        return progress

    def any_consumer_running(self):
        return not (
            self.has_finished_crawl()
            and self.has_finished_audit()
            and self.has_finished_grep()
        )

    def get_crawl_adjustment_ratio(self):
        return get_crawl_adjustment(self._lifecycle.get_run_time_seconds())

    def get_audit_adjustment_ratio(self):
        return get_audit_adjustment(
            self._lifecycle.get_run_time_seconds(), self.has_finished_crawl()
        )

    def get_grep_adjustment_ratio(self):
        return get_grep_adjustment(
            self._lifecycle.get_run_time_seconds(),
            self.has_finished_crawl(),
            self.has_finished_audit(),
        )

    def log_eta(self, msg):
        self._output.debug(f"[get_eta] {msg}")

    def get_eta(self):
        """Calculate the estimated number of seconds to complete the scan."""
        if self.has_finished_grep():
            self.log_eta("ETA is 0. Grep consumer has already finished.")
            return 0

        if self.has_finished_crawl() and self.has_finished_audit():
            self.log_eta(
                "Crawl and audit consumers have finished,"
                " ETA calculated using grep ETA."
            )
            return self.get_grep_eta()

        if self.has_finished_crawl() and not self.has_finished_audit():
            grep_eta = self.get_grep_eta()
            audit_eta = self.get_audit_eta()
            after_audit = 0.0
            if grep_eta >= audit_eta:
                after_audit = (grep_eta - audit_eta) * 0.1

            self.log_eta(
                "Crawl has finished. Using audit and grep ETAs"
                " to calculate overall ETA."
            )
            return audit_eta + after_audit

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

        return crawl_eta + audit_after_crawl * 0.75 + grep_after_crawl_audit * 0.05
