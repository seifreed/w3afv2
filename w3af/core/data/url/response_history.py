"""Track response outcomes used by the HTTP runtime policies."""

from collections import deque
from collections.abc import Callable

from w3af.core.data.url.constants import MAX_ERROR_COUNT, MAX_RESPONSE_COLLECT
from w3af.core.data.url.response_meta import SUCCESS, ResponseMeta


class ResponseHistory:
    """Store recent response metadata and derive transport health metrics."""

    def __init__(self) -> None:
        self._responses: deque[ResponseMeta] = deque(maxlen=MAX_RESPONSE_COLLECT)
        self.reset()

    def reset(self) -> None:
        self._responses.clear()
        self._responses.extend([ResponseMeta(True, SUCCESS)] * MAX_RESPONSE_COLLECT)

    def record_success(self, host, rtt) -> None:
        self._responses.append(ResponseMeta(True, SUCCESS, rtt=rtt, host=host))

    def record_failure(self, message, host, rtt) -> None:
        self._responses.append(ResponseMeta(False, message, host=host, rtt=rtt))

    def get_average_rtt(self, count, host=None):
        rtt_sum = 0.0
        sample_count = 0

        for response_meta in list(self._responses)[-count:]:
            if host is not None and response_meta.host != host:
                continue

            if response_meta.rtt is not None:
                rtt_sum += response_meta.rtt
                sample_count += 1

        if not sample_count:
            return None, 0

        return float(rtt_sum) / sample_count, sample_count

    def get_error_rate(self) -> int:
        total_failed = sum(
            not response_meta.successful for response_meta in self._responses
        )
        return int((total_failed / len(self._responses)) * 100)

    def should_stop_scan(self, is_server_reachable: Callable[[], bool]) -> bool:
        last_responses = list(self._responses)[-MAX_ERROR_COUNT:]
        first_result = last_responses[0]

        if first_result.successful and all(
            not response_meta.successful for response_meta in last_responses[1:]
        ):
            return not is_server_reachable()

        return False

    def get_recent_messages(self, count):
        return [response.message for response in list(self._responses)[-count:]]
