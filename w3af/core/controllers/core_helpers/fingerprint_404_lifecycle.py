"""Own the lifecycle of the scan-level 404 detector."""

from w3af.core.controllers.core_helpers.fingerprint_404 import Fingerprint404
from w3af.core.data.db.dbms import SQLiteDBMS


class Fingerprint404Lifecycle:
    """Create, reuse and release the detector associated with one core."""

    def __init__(self, output, configuration, db: SQLiteDBMS, uri_opener) -> None:
        self._output = output
        self._configuration = configuration
        self._db = db
        self._uri_opener = uri_opener
        self._detector: Fingerprint404 | None = None

    def start(self) -> None:
        """Replace the previous detector with a fresh scan detector."""
        self.cleanup()
        detector = Fingerprint404(self._output, self._configuration, db=self._db)
        detector.set_url_opener(self._uri_opener)
        self._detector = detector

    def is_404(self, http_response) -> bool:
        """Return whether the response matches the current 404 fingerprint."""
        detector = self._detector
        if detector is None:
            self.start()
            detector = self._detector
        if detector is None:
            raise RuntimeError("Fingerprint404 detector failed to start")
        return detector.is_404(http_response)

    def cleanup(self) -> None:
        """Release the detector cache and forget the detector instance."""
        if self._detector is None:
            return
        self._detector.cleanup()
        self._detector = None
