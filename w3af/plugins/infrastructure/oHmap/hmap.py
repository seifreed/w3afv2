#! /usr/bin/env python
#
#  Fingerprint a web server and identify its vendor/version/OS
#  Copyright (C) 2003  Dustin Lee
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Suite 500, Boston, MA  02110-1335  USA
#
#  You can reach me at <leed@cs.ucdavis.edu>
######################################################################

import ast
import glob
import os
import pprint
import re
import socket
import ssl
import time
from collections import namedtuple
from itertools import pairwise

from w3af import ROOT_PATH
from w3af.core.controllers.threads.threadpool import Pool
from w3af.core.exceptions import BaseFrameworkException

KNOWN_SERVERS_DIR = os.path.join(
    ROOT_PATH, "plugins", "infrastructure", "oHmap", "known.servers"
)
SOCKET_TIMEOUT = 10
SUBMIT_TRIES = 3
NO_RESPONSE_CODES = ("NO_RESPONSE_CODE", "NO_RESPONSE")
STATUS_LINE_RE = re.compile(r"^HTTP/1\.[01] [0-9]{3} [A-Z]{,10}")
RESPONSE_LINE_RE = re.compile("(HTTP/1\\.[01]) ([0-9]{3}) ([^\r\n]*)")

Target = namedtuple(
    "Target", ["host", "port", "use_ssl", "output", "user_agent"], defaults=(None,)
)


class request:
    """
    Collect elements needed to send a Request to an HTTP server
    """

    def __init__(self, target, method="GET", local_uri="/", version="1.0"):
        self.target = target
        self._output = target.output
        self.method = method
        self.local_uri = local_uri
        self.version = version
        self.headers = [["User-Agent", target.user_agent or "w3af.org"]]
        self.line_joiner = "\r\n"
        self.body = ""
        self.adhoc_method_line = ""

    def __str__(self):
        method_line = self.adhoc_method_line
        if not method_line:
            method_line = f"{self.method} {self.local_uri} HTTP/{self.version}"

        return (
            self.line_joiner.join(
                [method_line] + [f"{x}: {y}" for x, y in self.headers]
            )
            + (2 * self.line_joiner)
            + self.body
        )

    def get_connection(self):
        host, port = self.target.host, self.target.port

        try:
            s = socket.create_connection((host, port), timeout=SOCKET_TIMEOUT)
        except OSError as e:
            msg = 'hmap connection failed to %s:%s. Exception: "%s"'
            raise BaseFrameworkException(msg % (host, port, e)) from e

        if not self.target.use_ssl:
            return s

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        try:
            return context.wrap_socket(s, server_hostname=host)
        except OSError as e:
            s.close()
            msg = 'hmap SSL connection failed to %s:%s. Exception: "%s"'
            raise BaseFrameworkException(msg % (host, port, e)) from e

    def submit(self):
        self._output.debug("hmap is sending: " + str(self))

        wait_time = 1

        for _ in range(SUBMIT_TRIES):
            s = self.get_connection()

            try:
                s.send(str(self).encode("utf-8"))
                data = read_until_closed(s, self._output)
            except OSError as e:
                msg = 'hmap failed to exchange data with the server: "%s"'
                self._output.debug(msg % e)

                # Try again
                time.sleep(wait_time)
                wait_time *= 2
                continue
            finally:
                s.close()

            msg = f'hmap received: "{repr(data)[1:-1][:40]}..."'
            self._output.debug(msg)
            return response(data.decode("latin-1"))

        # Something happen... we just return an empty response
        return response("")

    def add_header(self, name, data):
        self.headers.append([name, data])


def read_until_closed(s, output):
    """
    :return: The bytes received until the server closes the connection, or
             until it stops sending data for SOCKET_TIMEOUT seconds.
    :raise OSError: When the connection fails before receiving any data
    """
    data = b""

    try:
        while chunk := s.recv(4096):
            data += chunk
    except OSError as e:
        # Servers which reject a request before reading all of it, because
        # it has too many headers for example, reset the connection after
        # sending the response. Others wait for the announced request body.
        if not data and not isinstance(e, TimeoutError):
            raise

        output.debug(f'hmap stopped reading from the server: "{e}"')

    return data


######################################################################


class response:
    """Read in Response from HTTP server and parse out elements of interest"""

    def __init__(self, raw_text):
        self.raw_text = raw_text
        self.headers = []
        self.body = ""
        self.__parse(raw_text)

    def __parse(self, text):
        if not text:
            self.response_code = "NO_RESPONSE"
            self.response_text = "NONE"
            return

        if not STATUS_LINE_RE.search(text):
            self.response_code = "NO_RESPONSE_CODE"  # HTTP/0.9 like
            self.response_text = "NONE"
            self.body = text
            return

        # Responses which have a "\r" before the first "\r\n" are split by "\n"
        crlf_index = text.find("\r\n")
        line_splitter = "\r\n" if text.find("\r") == crlf_index != -1 else "\n"

        response_lines = text.split(line_splitter)
        self.response_line = response_lines[0]
        response_line_match = RESPONSE_LINE_RE.search(text)
        assert response_line_match is not None
        self.response_code, self.response_text = response_line_match.groups()[1:]

        blank_index = len(response_lines)
        if "" in response_lines:
            blank_index = response_lines.index("")

        self.headers = response_lines[1:blank_index]
        # NOTE: !! actually don't need or want body to be split but don't
        #         really care at this point ...
        self.body = response_lines[blank_index:]

    def return_code(self):
        return self.response_code, self.response_text

    def header_data(self, name):
        """
        :return: The value of the first header which starts with name, matched
                 case-insensitively, or None when there is no such header.
        """
        prefix = name.lower()

        for h in self.headers:
            if h.lower().startswith(prefix):
                return h.split(": ", 1)[-1]

        return None

    def header_names(self):
        return [h.split(":", 1)[0] for h in self.headers]

    def servername(self):
        return self.header_data("Server")


######################################################################
# Functions for probing server and collecting characteristics


def get_fingerprint(target, threads):
    for characteristics in fingerprint.values():
        characteristics.clear()

    pool = Pool(
        worker_names="HMap", maxtasksperchild=2, processes=threads, max_queued_tasks=5
    )

    try:
        results = [pool.apply_async(func=probe, args=(target,)) for probe in PROBES]

        # Raise the exceptions found by the probes, if any
        for result in results:
            result.get()
    finally:
        pool.close()
        pool.join()

    fingerprint["SYNTACTIC"]["HEADER_ORDER"] = winnow_ordered_list(
        fingerprint["SYNTACTIC"]["HEADER_ORDER"]
    )
    return fingerprint


######################################################################
# Known test types for provoking characterisitcs
# Many tests are just "randomly" designed out of thin air
# but many come from reading the RFC and looking for things
# that implementors may have varied in implementations.
def basic_get(target):
    req = request(target)
    res = req.submit()
    get_characteristics("basic_get", res)


def basic_options(target):
    req = request(target, method="OPTIONS")
    res = req.submit()
    get_characteristics("basic_options", res)


def unknown_method(target):
    req = request(target, method="QWERTY")
    res = req.submit()
    get_characteristics("unknown_method", res)


def unauthorized_activity(target):

    # Removed the DELETE method so we don't remove a whole site without wanting to :)
    unauthorized_activities = (
        "OPTIONS",
        "TRACE",
        "GET",
        "HEAD",
        "PUT",
        "POST",
        "COPY",
        "MOVE",
        "MKCOL",
        "PROPFIND",
        "PROPPATCH",
        "LOCK",
        "UNLOCK",
        "SEARCH",
    )
    for ua in unauthorized_activities:
        req = request(target, method=ua)
        res = req.submit()
        get_characteristics("unauthorized_activity", res)


def nonexistant_object(target):
    req = request(target, local_uri="/asdfg.hjkl")
    res = req.submit()
    get_characteristics("nonexistant_object", res)


# ways to mess up the method line
# (nothing)METHOD(space)RELATIVE-URI(space)VERSION(line-sep)
# - replace any one of these with wrong thing
# - string together  variations of any of these
#   - number where expects letter or vice verse
#   - really LONG things
#   - invalid characters
#   - different file system conventions
#   - illegal paths "../../../"
#   - url encoding (hex, unicode, invalid of each)
#   - something instead of nothing and vice versa
#   - uppercase/lowercase


def malformed_method_line(target):
    malformed_methods = (
        "GET",  # 0 TODO: repeat all these with HEAD and OTHER
        "GET /",  # 1
        "GET / HTTP/999.99",
        "GET / HHTP/1.0",
        "GET / HTP/1.0",
        "GET / HHTP/999.99",
        #'GET / HHTP/1.0',
        "GET / hhtp/999.99",
        "GET / http/999.99",
        "GET / HTTP/Q.9",
        "GET / HTTP/9.Q",
        "GET / HTTP/Q.Q",  # 10
        "GET / HTTP/1.X",
        "GET / HTTP/1.10",
        "GET / HTTP/1.1.0",
        "GET / HTTP/1.2",
        "GET / HTTP/2.1",
        "GET / HTTP/1,0",
        # r'\GET / HTTP/1.0' or '\\GET / HTTP/1.0'
        #'GET / HTTP\1.0',
        #'GET / HTTP-1.0',
        #'GET / HTTP 1.0',
        "GET / HTTP/1.0X",
        "GET / HTTP/",
        #'get / http/1.0',
        #'qwerty / HTTP/1.0'
        #'GETX / HTTP/1.0'
        #' GET/HTTP/1.0',
        "GET/HTTP/1.0",
        "GET/ HTTP/1.0",  # 20
        "GET /HTTP/1.0",
        "GET/HTTP /1.0",
        "GET/HTTP/1 .0",
        "GET/HTTP/1. 0",
        "GET/HTTP/1.0 ",
        "GET / HTTP /1.0",  # etc....
        "HEAD /.\\ HTTP/1.0",  # indicates windows??
        "HEAD /asdfasdfasdfasdfasdf/../ HTTP/1.0",
        "HEAD /asdfasdfasdfasdfasdf/.. HTTP/1.0",
        "HEAD /./././././././././././././././ HTTP/1.0",
        # 30
        "HEAD /././././././qwerty/.././././././././ HTTP/1.0",
        #'HEAD ../ HTTP/1.0',
        "HEAD /.. HTTP/1.0",
        "HEAD /../ HTTP/1.0",
        "HEAD /../../../../../ HTTP/1.0",
        "HEAD .. HTTP/1.0",
        #'HEAD . HTTP/1.0',
        "HEAD\t/\tHTTP/1.0",
        "HEAD ///////////// HTTP/1.0",
        "Head / HTTP/1.0",
        "\nHEAD / HTTP/1.0",
        " \nHEAD / HTTP/1.0",  # 40
        " HEAD / HTTP/1.0",
        "HEAD / HQWERTY/1.0",
        #      'HEAD http://some.host.com/ HTTP/1.0',
        #      'HEAD hTTP://some.host.com/ HTTP/1.0',
        #      'HEAD http://some.host.com HTTP/1.0',
        f"HEAD {target.host} HTTP/1.0",
        #'HEAD hTTP://$url/ HTTP/1.0',
        #'HEAD http://$url HTTP/1.0',
        f"HEAD {target.host}",
        "HEAD http:// HTTP/1.0",
        "HEAD http:/ HTTP/1.0",
        "HEAD http: HTTP/1.0",
        "HEAD http HTTP/1.0",
        "HEAD h HTTP/1.0",
        #      'HEAD HTTP://some.host.com/ HTTP/1.0',
        #'HEAD HTTP://$url/ HTTP/1.0',
        "HEAD HTTP://qwerty.asdfg.com/ HTTP/1.0",  # 50
        "GET GET GET",
        "HELLO",
        #      'HEAD%00 / HTTP/1.0',
        "GET \0 / HTTP/1.0",
        "GET / \0 HTTP/1.0",
        "GET / HTTP/1.0\0",
        "GET / H",
        " GET / HTTP/1.0",
        " " * 1000 + "GET / HTTP/1.0",
        "GET" + " " * 1000 + "/ HTTP/1.0",
        "GET " + "/" * 1000 + " HTTP/1.0",  # 60
        "GET /" + " " * 1000 + "HTTP/1.0",
        "GET / " + "H" * 1000 + "TTP/1.0",
        "GET / " + "HTTP" + "/" * 1000 + "1.0",
        "GET / " + "HTTP/" + "1" * 1000 + ".0",
        "GET / " + "HTTP/1" + "." * 1000 + "0",
        "GET / " + "HTTP/1." + "0" * 1000,
        "GET / HTTP/1.0" + " " * 1000,
        "12345 GET / HTTP/1.0",
        "12345 / HTTP/1.0",
        # check if \0 is really a null
        "\0",  # 70
        "\0" * 1000,
        "\0" + "GET / HTTP/1.0",
        "\0" * 1000 + "GET / HTTP/1.0",
        "\r\n" * 1000 + "GET / HTTP/1.0",
        "Get / HTTP/1.0",
        "GET\0/\0HTTP/1.0",
        "GET . HTTP/1.0",
        "GET index.html HTTP/1.0",  # is this legal?
        "GET / HTTP/1.",
        "",  # 80
        " ",
        " " * 1000,
        "/",
        "/" * 1000,
        "GET FTP://asdfasdf HTTP/1.0",
        "GET / HTTP/1.0 X",
        # any or all parts or request URL encoded
        # >>> [hex(ord(x)) for x in "GET / HTTP/1.0"]
        # ['0x47', '0x45', '0x54', '0x20', '0x2f', '0x20', '0x48', '0x54', '0x54', '0x50', '0x2f', '0x31', '0x2e', '0x30']
        "%47ET / HTTP/1.0",
        "%47%45%54 / HTTP/1.0",
        "GET %2f HTTP/1.0",
        "GET %2F HTTP/1.0",  # 90
        "GET%20/ HTTP/1.0",
        "GET / FTP/1.0",
        r"GET \ HTTP/1.0",  # windows style
        #'GET \./',
        #'GET \.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\. HTTP/1.0'
        r"GET C:\ HTTP/1.0",
        "HTTP/1.0 / GET",  # and other permutations
        # try various escape sequences from c etal
        # \a = bell
        # \b = back space?
        "ALL YOUR BASE ARE BELONG TO US",
        'GET "/" HTTP/1.0',
        "GET '/' HTTP/1.0",
        "GET `/` HTTP/1.0",
        '"GET / HTTP/1.0"',  # 100
        '"GET / HTTP/1.0',
        '"GET" / HTTP/1.0',
        '""GET / HTTP/1.0',
        "GEX\bT / HTTP/1.0",  # espace characters
    )

    # print len(malformed_methods)

    for index, mm in enumerate(malformed_methods):
        req = request(target)
        req.adhoc_method_line = mm
        res = req.submit()
        get_characteristics("MALFORMED_" + ("000" + str(index))[-3:], res)


def large_binary_searcher(target, large_helper, largest, guesses=()):
    ranges = [(x, large_helper(target, x)) for x in [1, *guesses, largest]]

    while True:
        halfways = find_halfways(ranges)
        if not halfways:
            break
        for hw in halfways:
            ranges.append((hw, large_helper(target, hw)))
        ranges.sort()

    return minimize_ranges(ranges)


def group_ranges(ranges):
    """
    :param ranges: (size, response code) tuples, sorted by size
    :return: Lists with the consecutive ranges which share the response code
    """
    grouped_ranges: list[list[tuple[int, str]]] = []
    for r in ranges:
        if grouped_ranges and r[1] == grouped_ranges[-1][-1][1]:
            grouped_ranges[-1].append(r)
        else:
            grouped_ranges.append([r])

    return grouped_ranges


def find_halfways(ranges):
    # assumes they are sorted
    grouped_ranges = group_ranges(ranges)

    halfways = []
    for previous_group, next_group in pairwise(grouped_ranges):
        largest_previous = previous_group[-1]
        smallest_next = next_group[0]

        if (smallest_next[0] - largest_previous[0]) == 1:
            continue
        hw = ((smallest_next[0] - largest_previous[0]) // 2) + largest_previous[0]
        halfways.append(hw)

    return halfways


def minimize_ranges(ranges):
    # assumes they are sorted
    minimized = []
    for gr in group_ranges(ranges):
        minimized.append(gr[0])
        if len(gr) > 1:
            minimized.append(gr[-1])

    return minimized


# TODO: maybe do this recursively????
# TODO: remember that header size et all are configurable in apache


def long_url_helper(target, size):
    req = request(target, local_uri=("/" + ("a" * size)))
    res = req.submit()
    get_characteristics("LONG_URL_RANGES", res)
    return res.response_code


def long_url_ranges(target):
    # TODO: base these on "best guess" of what talking to
    #      e.g. if think it's apache 1.3.9 then use those to avoid
    #      so many long requests
    initial_guesses = [
        99,
        100,
        201,
        202,
        208,
        209,
        210,
        211,
        254,
        255,
        256,
        765,
        766,
        8079,
        8080,
        8176,
        8177,
    ]
    ranges = large_binary_searcher(
        target, long_url_helper, 10000, guesses=initial_guesses
    )
    add_characteristic("SEMANTIC", "LONG_URL_RANGES", ranges)


def long_default_helper(target, size):
    req = request(target, local_uri=("/" * size))
    res = req.submit()
    get_characteristics("LONG_DEFAULT_RANGES", res)
    return res.response_code


def long_default_ranges(target):
    ranges = large_binary_searcher(target, long_default_helper, 10000)
    add_characteristic("SEMANTIC", "LONG_DEFAULT_RANGES", ranges)


def many_header_helper(target, size):
    req = request(target)

    for i in range(size):
        req.add_header(
            "HEADER" + ("0000000000" + str(i)[-10:]), ("0000000000" + str(i))[-10:]
        )

    res = req.submit()
    get_characteristics("MANY_HEADER_RANGES", res)

    return res.response_code


def many_header_ranges(target):
    initial_guesses = [99, 100, 228, 229]
    ranges = large_binary_searcher(
        target, many_header_helper, 10000, guesses=initial_guesses
    )
    add_characteristic("SEMANTIC", "MANY_HEADER_RANGES", ranges)


def large_header_helper(target, size):
    req = request(target)
    req.add_header("LARGE_HEADER", "a" * size)
    res = req.submit()
    get_characteristics("LARGE_HEADER_RANGES", res)
    return res.response_code


def large_header_ranges(target):
    initial_guesses = [
        8176,
        8177,
    ]
    ranges = large_binary_searcher(
        target, large_header_helper, 10000, guesses=initial_guesses
    )
    add_characteristic("SEMANTIC", "LARGE_HEADER_RANGES", ranges)


def unavailable_accept(target):
    req = request(target)
    req.add_header("Accept", "qwer/asdf")
    res = req.submit()
    get_characteristics("unavailable_accept", res)


def fake_content_length(target):
    req = request(target)
    req.add_header("Content-Length", "1000000000")
    req.body = "qwerasdfzxcv"
    res = req.submit()
    get_characteristics("fake_content_length", res)


PROBES = (
    basic_get,
    basic_options,
    unknown_method,
    unauthorized_activity,
    nonexistant_object,
    malformed_method_line,
    long_url_ranges,
    long_default_ranges,
    many_header_ranges,
    large_header_ranges,
    unavailable_accept,
    fake_content_length,
)

# The characteristics of the server which is being fingerprinted
fingerprint: dict[str, dict] = {
    "LEXICAL": {},
    "SYNTACTIC": {},
    "SEMANTIC": {},
}

# (header name, characteristic) of the headers whose values are compared
ORDERED_HEADERS = (
    ("Allow", "ALLOW_ORDER"),
    ("Public", "PUBLIC_ORDER"),
    ("Vary", "VARY_ORDER"),
    ("ETag", "ETag"),
)


def add_characteristic(category, name, value, data_type=None):
    # just add if not already in there
    if name not in fingerprint[category]:
        # TODO: probably don't need a data type just look at data...
        if data_type == "LIST":
            value = [value]
        fingerprint[category][name] = value
        return
    # don't duplicate
    if fingerprint[category][name] == value:
        return
    # create or add to list as necessary
    if not isinstance(fingerprint[category][name], list):
        fingerprint[category][name] = [fingerprint[category][name], value]
    elif value not in fingerprint[category][name]:
        fingerprint[category][name].append(value)


def get_characteristics(test_name, res):
    response_code, response_text = res.return_code()
    has_response_code = response_code not in NO_RESPONSE_CODES

    if has_response_code:
        add_characteristic("LEXICAL", response_code, response_text)
        add_characteristic("LEXICAL", "SERVER_NAME", res.servername())

    if test_name.endswith("RANGES"):
        return  # only need the code and text

    for header_name, characteristic in ORDERED_HEADERS:
        data = res.header_data(header_name)
        if data is not None:
            add_characteristic("SYNTACTIC", characteristic, data)

    if test_name.startswith("MALFORMED_"):
        add_characteristic("SEMANTIC", test_name, response_code)

    header_names = res.header_names() if has_response_code else []
    add_characteristic("SYNTACTIC", "HEADER_ORDER", header_names, data_type="LIST")


# 'HEADER_ORDER': [   [   'Date',
#                        'Server',
#                        'Last-Modified',
#                        'ETag',
#                        'Accept-Ranges',
#                        'Content-Length',
#                        'Connection',
#                        'Content-Type'],
#                    [   'Date',
#                        'Server',
#                        'Content-Length',
#                        'Allow',
#                        'Connection'],
#                    ['Date', 'Server', 'Connection']],
# clean up redundancies in lists of lists


def winnow_ordered_list(ordered_list):
    if len(ordered_list) < 2:
        return ordered_list

    ordered_list.sort(key=len)

    result = []
    for index, elem in enumerate(ordered_list[:-1]):
        if not any(
            is_partial_ordered_sublist(elem, other)
            for other in ordered_list[index + 1 :]
        ):
            result.append(elem)
    result.append(ordered_list[-1])
    return result


def is_partial_ordered_sublist(small, large):
    if len(small) > len(large):
        return False

    try:
        positions = [large.index(x) for x in small]
    except ValueError:
        return False

    return positions == sorted(positions)


######################################################################
# Functions for comparing to known profiles
#

LEXICAL_CODES = (
    "200",
    "207",
    "301",
    "302",
    "400",
    "401",
    "403",
    "404",
    "405",
    "406",
    "411",
    "413",
    "414",
    "500",
    "501",
)

SEMANTIC_NAMES = (
    *("MALFORMED_" + ("000" + str(num))[-3:] for num in range(105)),
    "LONG_URL_RANGES",
    "LONG_DEFAULT_RANGES",
)


def find_most_similar(known_servers, subject):
    """
    :return: [server, (matches, mismatches, unknowns)] for each known server
    """
    return [[server, compare_fingerprints(server, subject)] for server in known_servers]


def compare_fingerprints(server, subject):
    matches = 0
    mismatches = 0
    unknowns = 0

    # LEXICAL
    for code in LEXICAL_CODES:
        known_server_text = server["LEXICAL"].get(code, "")
        subject_server_text = subject["LEXICAL"].get(code, "")

        if known_server_text == "" or subject_server_text == "":
            unknowns += 1
        elif known_server_text == subject_server_text:
            matches += 1
        else:
            mismatches += 1

    # SYNTACTIC
    # allow order
    known_server_allows = server["SYNTACTIC"].get("ALLOW_ORDER", "")
    subject_server_allows = subject["SYNTACTIC"].get("ALLOW_ORDER", "")

    if not (known_server_allows and subject_server_allows):
        unknowns += 1
    elif known_server_allows == subject_server_allows:
        matches += 1
    else:
        mismatches += 1

    # SEMANTIC
    # malformed method lines, long URL and long default "/" ranges
    for name in SEMANTIC_NAMES:
        if server["SEMANTIC"][name] == subject["SEMANTIC"].get(name):
            matches += 1
        else:
            mismatches += 1

    return matches, mismatches, unknowns


def load_known_servers(fingerprint_dir):
    """
    :return: The fingerprints of the known servers, read from the files which
             ship with w3af and contain Python literal data.
    """
    known_servers = []

    for f in sorted(glob.glob(os.path.join(fingerprint_dir, "*"))):
        with open(f) as ksf:
            signature_source = ksf.read()

        try:
            known_servers.append(ast.literal_eval(signature_source))
        except (SyntaxError, ValueError) as exc:
            raise BaseFrameworkException(
                'The signature file "' + f + '" has an invalid syntax.'
            ) from exc

    return known_servers


def write_fingerprint_file(fp, server):
    """
    Write the fingerprint to a file in the current directory, so the user can
    send it to the w3af developers.

    :return: The name of the fingerprint file
    """
    filename = f"hmap-fingerprint-{server}-0"

    try:
        with open(filename, "w") as fd:
            pprint.PrettyPrinter(stream=fd).pprint(fp)
    except OSError as e:
        raise BaseFrameworkException(
            "Cannot open fingerprint file. Error:" + str(e)
        ) from e

    return filename


######################################################################
# This was added by Andres Riancho to make hmap work inside w3af
# it is a "copy" of the "main" with a lot of default parameters :P


def testServer(
    use_ssl,
    server,
    port,
    matchCount,
    generateFP,
    threads,
    output,
    user_agent="w3af.org",
):
    fp = get_fingerprint(Target(server, port, use_ssl, output, user_agent), threads)
    known_servers = load_known_servers(KNOWN_SERVERS_DIR)

    if generateFP:
        write_fingerprint_file(fp, server)

    scores = find_most_similar(known_servers, fp)
    # Some known servers have a list of names, compare them as strings
    scores.sort(
        key=lambda score: (-score[1][0], str(score[0]["LEXICAL"]["SERVER_NAME"]))
    )

    return [
        server_entry["LEXICAL"]["SERVER_NAME"]
        for server_entry, _ in scores[:matchCount]
    ]
