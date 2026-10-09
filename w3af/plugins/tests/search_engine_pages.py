"""
search_engine_pages.py

Copyright 2026 w3af contributors

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

Canned search engine result pages, in the format returned by the real
search engines, used by the plugin tests to answer the search requests
without reaching the internet.
"""

import json
import re
import urllib.parse

from w3af.plugins.tests.helper import MockResponse

BING_SEARCH_URL_RE = re.compile(r"https?://www\.bing\.com/search\?.*")

GOOGLE_AJAX_SEARCH_URL_RE = re.compile(
    r"https?://ajax\.googleapis\.com/ajax/services/search/web\?.*"
)
GOOGLE_MOBILE_SEARCH_URL_RE = re.compile(r"https?://www\.google\.com/xhtml\?.*")
GOOGLE_STANDARD_SEARCH_URL_RE = re.compile(r"https?://www\.google\.com/search\?.*")


def bing_results_page(urls):
    """
    :return: A Bing result page linking to each of the urls
    """
    results = "".join(
        f'<li class="b_algo"><h2><a href="{url}" h="ID=SERP,{index}.1">'
        f"Result {index}</a></h2></li>"
        for index, url in enumerate(urls, start=5100)
    )
    return (
        "<html><body>"
        f'<ol id="b_results">{results}</ol>'
        '<a href="http://go.microsoft.com/fwlink/" h="ID=SERP,9000.1">Help</a>'
        "</body></html>"
    )


def bing_search_response(urls):
    return MockResponse(BING_SEARCH_URL_RE, bing_results_page(urls))


def google_ajax_results(urls):
    """
    :return: A Google AJAX API JSON response with one result per url
    """
    results = [{"url": url, "titleNoFormatting": url} for url in urls]
    return json.dumps(
        {
            "responseData": {"results": results},
            "responseDetails": None,
            "responseStatus": 200,
        }
    )


def google_results_page(urls, extra_html=""):
    """
    :return: A Google (standard or mobile) result page linking to the urls
    """
    results = "".join(
        f'<h3 class="r"><a href="/url?q={urllib.parse.quote_plus(url)}'
        f'&amp;sa=U&amp;ved=0ahUKE">{url}</a></h3>'
        for url in urls
    )
    return f"<html><body><div id='ires'>{results}</div>{extra_html}</body></html>"


def google_search_responses(urls, extra_html=""):
    """
    :return: The MockResponses answering the Google AJAX API, mobile and
             standard searches with links to the urls
    """
    return [
        MockResponse(
            GOOGLE_AJAX_SEARCH_URL_RE,
            google_ajax_results(urls),
            content_type="application/json",
        ),
        MockResponse(GOOGLE_MOBILE_SEARCH_URL_RE, google_results_page(urls)),
        MockResponse(
            GOOGLE_STANDARD_SEARCH_URL_RE, google_results_page(urls, extra_html)
        ),
    ]
