"""Control scan-wide pause and stop state for outgoing requests."""

import time

from w3af.core.exceptions import ScanMustStopByUserRequest, ScanMustStopException


class ScanRequestControl:
    """Coordinate user pause/stop state shared by request senders."""

    def __init__(self):
        self._user_paused = False
        self._user_stopped = False
        self._stop_exception: ScanMustStopException | None = None

    @property
    def stop_exception(self) -> ScanMustStopException | None:
        return self._stop_exception

    @stop_exception.setter
    def stop_exception(self, exception: ScanMustStopException | None) -> None:
        self._stop_exception = exception

    def pause(self, pause_yes_no):
        self._user_paused = pause_yes_no

    def stop(self):
        self._user_stopped = True

    def clear(self):
        self._user_stopped = False
        self._user_paused = False
        self._stop_exception = None

    def raise_if_should_stop(self):
        if self._stop_exception is not None:
            raise self._stop_exception

    def pause_and_stop(self):
        """Wait while paused and raise any stop request."""

        def analyze_state():
            if self._user_stopped:
                raise ScanMustStopByUserRequest("The user stopped the scan.")

            self.raise_if_should_stop()

        while self._user_paused:
            time.sleep(0.2)
            analyze_state()

        analyze_state()
