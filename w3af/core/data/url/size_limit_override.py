"""Temporarily disable the configured response size limit."""

from contextlib import contextmanager


class SizeLimitOverride:
    """Temporarily raise the configured maximum response size."""

    def __init__(self, configuration) -> None:
        self._configuration = configuration

    @contextmanager
    def apply(self, respect_size_limit):
        if respect_size_limit:
            yield
            return

        original_size = self._configuration.get("max_file_size")
        self._configuration.save("max_file_size", 10**10)

        try:
            yield
        finally:
            self._configuration.save("max_file_size", original_size)
