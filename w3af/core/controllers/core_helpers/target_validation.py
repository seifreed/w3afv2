"""Validation helpers for configured scan targets."""

import logging

import w3af.core.controllers.output_manager as om
import w3af.core.data.kb.config as cf
from w3af.core.data.url.extended_urllib import MAX_ERROR_COUNT
from w3af.core.exceptions import ScanMustStopByUserRequest, ScanMustStopException

logger = logging.getLogger(__name__)


def verify_target_server_up(w3af_core):
    """Verify that the configured targets answer HTTP requests."""
    sent_requests = 0

    msg = (
        "The remote web server is not answering our HTTP requests,"
        " multiple errors have been found while trying to GET a response"
        " from the server.\n"
        "\n"
        "In most cases this means that the configured target is"
        " incorrect, the port is closed, there is a firewall blocking"
        " our packets or there is no HTTP daemon listening on that"
        " port.\n"
        "\n"
        "Please verify your target configuration and try again. The"
        " tested targets were:\n"
        "\n"
        " %s\n"
    )

    targets = cf.cf.get("targets")

    while sent_requests < MAX_ERROR_COUNT * 1.5:
        for url in targets:
            try:
                w3af_core.uri_opener.GET(url, cache=False)
            except ScanMustStopByUserRequest:
                raise
            except Exception as e:
                logger.debug(
                    "Unhandled exception in verify_target_server_up()",
                    exc_info=True,
                )
                dbg = 'Exception found during verify_target_server_up: "%s"'
                om.out.debug(dbg % e)

                target_list = "\n".join(f" - {url}\n" for url in targets)

                raise ScanMustStopException(msg % target_list)
            else:
                sent_requests += 1
