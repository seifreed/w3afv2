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
    for handler in logger.handlers[:]:
        if isinstance(handler, OutputManagerLogHandler):
            logger.removeHandler(handler)
    logger.addHandler(OutputManagerLogHandler(output))
    logger.setLevel(logging.DEBUG)
    logger.propagate = False


def remove_data_logging(output) -> None:
    """Remove the data logger handler associated with ``output``."""
    logger = logging.getLogger("w3af.core.data")
    for handler in logger.handlers[:]:
        if isinstance(handler, OutputManagerLogHandler) and handler._output is output:
            logger.removeHandler(handler)
