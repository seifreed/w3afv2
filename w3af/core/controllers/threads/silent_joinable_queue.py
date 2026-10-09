from multiprocessing.queues import JoinableQueue


class SilentJoinableQueue(JoinableQueue):
    """
    A joinable queue which silently ignores the broken pipe errors that the
    feeder thread raises when the reader goes away while the scan is shutting
    down.

    The standard library already supports this through the ``_ignore_epipe``
    flag used by its feeder thread, so we only need to enable it.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ignore_epipe = True
