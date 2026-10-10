"""Render the framework status for external consumers."""

from typing import Any


class StatusPresenter:
    """Build UI-facing status representations from a status provider."""

    def __init__(self, status):
        self._status = status

    def as_dict(self) -> dict[str, Any]:
        """Return the status representation used by JSON consumers."""

        def serialize_fuzzable_request(fuzzable_request):
            if fuzzable_request is None:
                return fuzzable_request

            return f"{fuzzable_request.get_method()} {fuzzable_request.get_uri()}"

        crawl_fuzzable_request = serialize_fuzzable_request(
            self._status.get_current_fuzzable_request("crawl")
        )
        audit_fuzzable_request = serialize_fuzzable_request(
            self._status.get_current_fuzzable_request("audit")
        )

        eta_seconds = self._status.get_eta()
        eta = self._status.epoch_eta_to_string(eta_seconds)
        progress = self._status.get_progress_percentage(eta=eta_seconds)

        return {
            "status": self._status.get_simplified_status(),
            "is_paused": self._status.is_paused(),
            "is_running": self._status.is_running(),
            "active_plugin": {
                "crawl": self._status.get_running_plugin("crawl"),
                "audit": self._status.get_running_plugin("audit"),
            },
            "current_request": {
                "crawl": crawl_fuzzable_request,
                "audit": audit_fuzzable_request,
            },
            "queues": {
                "crawl": {
                    "input_speed": self._status.get_crawl_input_speed(),
                    "output_speed": self._status.get_crawl_output_speed(),
                    "length": self._status.get_crawl_qsize(),
                    "processed_tasks": self._status.get_crawl_processed_tasks(),
                },
                "audit": {
                    "input_speed": self._status.get_audit_input_speed(),
                    "output_speed": self._status.get_audit_output_speed(),
                    "length": self._status.get_audit_qsize(),
                    "processed_tasks": self._status.get_audit_processed_tasks(),
                },
                "grep": {
                    "input_speed": self._status.get_grep_input_speed(),
                    "output_speed": self._status.get_grep_output_speed(),
                    "length": self._status.get_grep_qsize(),
                    "processed_tasks": self._status.get_grep_processed_tasks(),
                },
            },
            "eta": {
                "crawl": self._status.epoch_eta_to_string(self._status.get_crawl_eta()),
                "audit": self._status.epoch_eta_to_string(self._status.get_audit_eta()),
                "grep": self._status.epoch_eta_to_string(self._status.get_grep_eta()),
                "all": eta,
            },
            "rpm": self._status.get_rpm(),
            "sent_request_count": self._status.get_sent_request_count(),
            "progress": progress,
        }

    def long_status(self) -> str:
        """Return the human-readable status used by console consumers."""
        if not self._status.is_running():
            return self._status.get_status()

        eta_seconds = self._status.get_eta()

        data = {
            "status": self._status.get_status(),
            "cin": self._status.get_crawl_input_speed(),
            "cout": self._status.get_crawl_output_speed(),
            "clen": self._status.get_crawl_qsize(),
            "ceta": self._status.epoch_eta_to_string(self._status.get_crawl_eta()),
            "ain": self._status.get_audit_input_speed(),
            "aout": self._status.get_audit_output_speed(),
            "alen": self._status.get_audit_qsize(),
            "aeta": self._status.epoch_eta_to_string(self._status.get_audit_eta()),
            "gin": self._status.get_grep_input_speed(),
            "gout": self._status.get_grep_output_speed(),
            "glen": self._status.get_grep_qsize(),
            "geta": self._status.epoch_eta_to_string(self._status.get_grep_eta()),
            "perc": self._status.get_progress_percentage(eta=eta_seconds),
            "eta": self._status.epoch_eta_to_string(eta_seconds),
            "rpm": self._status.get_rpm(),
        }

        status_str = "%(status)s\n"
        status_str += (
            "Crawl phase: In (%(cin).2f URLs/min)"
            " Out (%(cout).2f URLs/min) Pending (%(clen)i URLs)"
            " ETA (%(ceta)s)\n"
        )
        status_str += (
            "Audit phase: In (%(ain).2f URLs/min)"
            " Out (%(aout).2f URLs/min) Pending (%(alen)i URLs)"
            " ETA (%(aeta)s)\n"
        )
        status_str += (
            "Grep phase: In (%(gin).2f URLs/min)"
            " Out (%(gout).2f URLs/min) Pending (%(glen)i URLs)"
            " ETA (%(geta)s)\n"
        )
        status_str += "Requests per minute: %(rpm)s\n\n"
        status_str += "Overall scan progress: %(perc)s%%\n"
        status_str += "Time to complete scan: %(eta)s\n"

        return status_str % data
