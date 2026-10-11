"""Track bounded metrics for requests sent by an opener."""

from w3af.core.data.misc.lru import SynchronizedLRUDict


class RequestMetrics:
    """Keep request counts and per-debugging-id round-trip times."""

    def __init__(self) -> None:
        self._rtt_sum_by_debugging_id = SynchronizedLRUDict(capacity=128)
        self._total_requests = 0

    def increment_requests(self) -> None:
        self._total_requests += 1

    def reset_total_requests(self) -> None:
        self._total_requests = 0

    def get_total_requests(self) -> int:
        return self._total_requests

    def track_rtt(self, http_response: object, debugging_id: object) -> None:
        if not hasattr(http_response, "get_wait_time"):
            return

        rtt = http_response.get_wait_time()
        rtt_sum = self._rtt_sum_by_debugging_id.get(debugging_id, default=None)
        self._rtt_sum_by_debugging_id[debugging_id] = (
            rtt if rtt_sum is None else rtt_sum + rtt
        )

    def get_rtt(self, debugging_id: object) -> float | None:
        if debugging_id is None:
            return None

        return self._rtt_sum_by_debugging_id.get(debugging_id, default=None)

    def clear_rtt(self) -> None:
        self._rtt_sum_by_debugging_id.clear()
