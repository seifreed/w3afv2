import logging


class OutputManagerLogHandler(logging.Handler):
    def __init__(self, output):
        super().__init__()
        self._output = output

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if record.levelno >= logging.ERROR:
            self._output.error(message)
        elif record.levelno >= logging.INFO:
            self._output.information(message)
        else:
            self._output.debug(message)


def configure_data_logging(output) -> None:
    logger = logging.getLogger("w3af.core.data")
    if not any(
        isinstance(handler, OutputManagerLogHandler) for handler in logger.handlers
    ):
        logger.addHandler(OutputManagerLogHandler(output))
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
