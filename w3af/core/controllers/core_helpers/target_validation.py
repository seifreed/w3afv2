"""Validation helpers for configured scan targets."""

import logging
from contextlib import contextmanager

import w3af.core.data.kb.config as cf
from w3af.core.controllers.core_helpers.fingerprint_404 import is_404
from w3af.core.data.kb.info import Info
from w3af.core.data.url.extended_urllib import MAX_ERROR_COUNT
from w3af.core.exceptions import ScanMustStopByUserRequest, ScanMustStopException

logger = logging.getLogger(__name__)


def verify_target_server_up(w3af_core, output):
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
                output.debug(dbg % e)

                target_list = "\n".join(f" - {url}\n" for url in targets)

                raise ScanMustStopException(msg % target_list)
            else:
                sent_requests += 1


@contextmanager
def _scan_must_stop_on_error(description, output):
    """Convert an unexpected target error into a scan-stop exception."""
    try:
        yield
    except ScanMustStopByUserRequest:
        raise
    except Exception as e:
        logger.debug(description, exc_info=True)
        msg = f'{description}: "{e}" ({e.__class__.__name__})'
        output.debug(msg)
        raise ScanMustStopException(msg) from e


def _get_target(w3af_core, url, step, output, **kwargs):
    """Send a GET request and normalize unexpected target failures."""
    with _scan_must_stop_on_error(f"Exception found during {step}", output):
        return w3af_core.uri_opener.GET(url, **kwargs)


def replace_targets_with_redir(w3af_core, output):
    """Replace targets with same-domain redirect destinations."""
    targets = cf.cf.get("targets")
    new_targets = []

    for url in targets:
        http_response = _get_target(
            w3af_core,
            url,
            "replace_targets_with_redir()",
            output,
            cache=False,
            follow_redirects=True,
        )
        redir_uri = http_response.get_redirect_destination()

        if redir_uri and not http_response.does_redirect_outside_target():
            new_targets.append(redir_uri)
        else:
            new_targets.append(url)

    cf.cf.save("targets", new_targets)


def alert_if_target_is_301_all(w3af_core, knowledge_base, output):
    """Report a target that redirects all traffic outside its scope."""
    site_does_redirect = False
    msg = (
        "The configured target domain redirects all HTTP requests to a"
        " different location. The most common scenarios are:\n"
        "\n"
        "    * HTTP redirect to HTTPS\n"
        "    * domain.com redirect to www.domain.com\n"
        "\n"
        "While the scan engine can identify URLs and vulnerabilities"
        " using the current configuration, it might be wise to start"
        " a new scan setting the target URL to the redirect target.\n"
        "\n"
        "Depending on multiple factors, this configuration might also"
        " reduce the effectiveness of the scanner 404 page detection,"
        " leading to false positives in both identified URLs and"
        " vulnerabilities."
    )

    targets = cf.cf.get("targets")

    for url in targets:
        http_response = _get_target(
            w3af_core, url, "alert_if_target_is_301_all()", output, cache=False
        )
        if http_response.does_redirect_outside_target():
            site_does_redirect = True
            break

    if site_does_redirect:
        name = "Target redirect"
        info = Info(name, msg, http_response.id, name)
        info.set_url(url)
        info.add_to_highlight(http_response.get_redir_url().url_string)

        knowledge_base.append_uniq("core", "core", info)
        output.report_finding(info)

    return site_does_redirect


def setup_404_detection(w3af_core, output):
    """Initialize 404 detection for each configured target."""
    targets_with_404 = []

    for url in cf.cf.get("targets"):
        response = _get_target(
            w3af_core, url, "_setup_404_detection()", output, cache=True
        )

        failure = (
            "Failed to initialize the 404 detection using HTTP"
            f' response from "{url}"'
        )
        with _scan_must_stop_on_error(failure, output):
            current_target_is_404 = is_404(response)

        if current_target_is_404:
            targets_with_404.append(url)

    if targets_with_404:
        urls = "".join(f" - {u.url_string}\n" for u in targets_with_404)
        output.information(
            "w3af identified the user-configured URLs listed"
            " below as non-existing pages (404). This could"
            " result in a scan with low test coverage: some"
            " application areas might not be scanned.\n"
            "\n"
            "Please manually verify that these URLs exist"
            " and, consider running a new scan with different"
            " targets.\n"
            "\n"
            f"{urls}"
            "\n"
            "In some scenarios it might be possible to fix"
            " this issue adding one or more target URLs to the"
            " `never_ssl` configuration parameter in `http-settings."
            " This will make sure that specific URLs are never"
            " seen as non-existing (404).\n"
        )
