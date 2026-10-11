"""Coordinate the public scan execution flow."""


class ScanExecutionController:
    """Run one scan while preserving its startup and shutdown order."""

    def __init__(
        self,
        output,
        output_manager,
        plugins,
        scan_start_lifecycle,
        scan_end_lifecycle,
        strategy_runner,
        get_strategy,
        get_status,
        verify_environment,
        get_version,
    ) -> None:
        self._output = output
        self._output_manager = output_manager
        self._plugins = plugins
        self._scan_start_lifecycle = scan_start_lifecycle
        self._scan_end_lifecycle = scan_end_lifecycle
        self._strategy_runner = strategy_runner
        self._get_strategy = get_strategy
        self._get_status = get_status
        self._verify_environment = verify_environment
        self._get_version = get_version

    def start(self) -> None:
        """Start and finalize a scan, including expected failure handling."""
        self._output.debug("Called w3afCore.start()")
        self._scan_start_lifecycle.start()
        self._verify_environment_or_raise()
        self._log_enabled_plugins()
        self._scan_start_lifecycle.mark_scan_started()
        self._output.debug(
            f"Starting the scan using w3af version {self._get_version()}"
        )

        try:
            strategy = self._get_strategy()
            status = self._get_status()
            self._strategy_runner.run(strategy, status.scans_completed)
        finally:
            self._finish_scan()

    def _verify_environment_or_raise(self) -> None:
        try:
            self._verify_environment()
        except Exception as exception:
            error = (
                'verify_environment() raised an exception: "%s". This'
                " should never happen. Are you (UI developer) sure that"
                " you called verify_environment() *before* start() ?"
            )
            self._output.error(error % exception)
            raise

    def _log_enabled_plugins(self) -> None:
        self._output_manager.log_enabled_plugins(
            self._plugins.get_all_enabled_plugins(),
            self._plugins.get_all_plugin_options(),
        )

    def _finish_scan(self) -> None:
        status = self._get_status()
        self._output.information(f"Scan finished in {status.get_scan_time()}")
        self._output.information("Stopping the core...")
        self._get_strategy().stop()
        self._scan_end_lifecycle.finish()

        # This must remain the final operation to avoid scan-state races.
        status.scan_finished()
