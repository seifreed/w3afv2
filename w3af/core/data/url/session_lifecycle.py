"""Manage the lifecycle of an ExtendedUrllib session."""


class SessionLifecycle:
    """Coordinate opener creation and scan-session cleanup."""

    def __init__(
        self,
        get_settings,
        request_control,
        response_history,
        reset_total_requests,
        reset_exploit_mode,
        clear_timeout,
    ):
        self._get_settings = get_settings
        self._request_control = request_control
        self._response_history = response_history
        self._reset_total_requests = reset_total_requests
        self._reset_exploit_mode = reset_exploit_mode
        self._clear_timeout = clear_timeout
        self._opener = None

    @property
    def opener(self):
        return self._opener

    def clear(self):
        """Clear all state accumulated during the scanner run."""
        self._request_control.clear()
        self._reset_total_requests()
        self._reset_exploit_mode()
        self._response_history.reset()

    def end(self):
        """Release resources owned by this session."""
        self._opener = None

        self.clear()
        self._clear_timeout()

        settings = self._get_settings()
        settings.clear_cookies()
        settings.clear_cache()
        settings.close_connections()

    def restart(self):
        self.end()

    def setup(self):
        """Build an opener when settings changed or no opener exists."""
        settings = self._get_settings()
        if settings.need_update or self._opener is None:
            settings.need_update = False
            settings.build_openers()
            self._opener = settings.get_custom_opener()

            self._clear_timeout()
