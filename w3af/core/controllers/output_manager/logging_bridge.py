import logging

import w3af.core.controllers.output_manager as om


class OutputManagerLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if record.levelno >= logging.ERROR:
            om.out.error(message)
        elif record.levelno >= logging.INFO:
            om.out.information(message)
        else:
            om.out.debug(message)


def configure_data_logging() -> None:
    logger = logging.getLogger("w3af.core.data")
    if not any(
        isinstance(handler, OutputManagerLogHandler) for handler in logger.handlers
    ):
        logger.addHandler(OutputManagerLogHandler())
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
