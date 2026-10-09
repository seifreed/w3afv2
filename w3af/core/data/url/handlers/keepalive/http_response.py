import http.client

from w3af.core.data.constants.response_codes import NO_CONTENT
from w3af.core.data.kb.config import cf

from .utils import debug


class HTTPResponse(http.client.HTTPResponse):
    # we need to subclass HTTPResponse in order to
    #
    # 1) read the whole body once and allow multiple reads of it
    # 2) return the connection to the pool when the response is closed
    # 3) add info() and geturl() methods
    # 4) handle cases where the remote server returns two content-length
    #    headers

    def __init__(self, sock, debuglevel=0, method=None):
        http.client.HTTPResponse.__init__(self, sock, debuglevel, method=method)
        self.fileno = sock.fileno
        self.code = None
        self._handler = None  # inserted by the handler later
        self._host = None  # (same)
        self._url = None  # (same)
        self._connection = None  # (same)
        self._method = method
        self._multiread = None
        self._encoding = None
        self._time = None

    def geturl(self):
        return self._url

    def get_encoding(self):
        return self._encoding

    def set_encoding(self, enc):
        self._encoding = enc

    encoding = property(get_encoding, set_encoding)

    def set_wait_time(self, t):
        self._time = t

    def get_wait_time(self):
        return self._time

    def _raw_read(self):
        """
        Read the whole body from the socket. This is the original read
        function from httplib with a minor modification that allows me to
        check the size of the file being fetched, and drop it if it is too big.
        """
        if self.fp is None:
            return b""

        max_file_size = cf.get("max_file_size") or None
        if max_file_size and self.length is not None and self.length > max_file_size:
            self.status = NO_CONTENT
            self.reason = "No Content"  # Reason-Phrase
            self.close()
            return b""

        if self.chunked:
            return self._read_chunked(None)

        if self.length is None:
            s = self.fp.read()
        else:
            s = self._safe_read(self.length)
            self.length = 0
        self.close()  # we read everything
        return s

    def begin(self):
        if self.msg is not None:
            # we've already started reading the response
            return

        # read until we get a non-100 response
        while True:
            version, status, reason = self._read_status()
            if status != http.client.CONTINUE:
                break
            # skip the header from the 100 response
            while True:
                skip = self.fp.readline(http.client._MAXLINE + 1)
                if len(skip) > http.client._MAXLINE:
                    raise http.client.LineTooLong("header line")
                if not skip.strip():
                    break

        self.status = status
        self.reason = reason.strip()
        if version == "HTTP/1.0":
            self.version = 10
        elif version.startswith("HTTP/1."):
            self.version = 11  # use HTTP/1.1 code for HTTP/1.x where x>=1
        elif version == "HTTP/0.9":
            self.version = 9
        else:
            raise http.client.UnknownProtocol(version)

        if self.version == 9:
            self.length = None
            self.chunked = 0
            self.will_close = 1
            self.msg = http.client.HTTPMessage()
            return

        self.msg = http.client.parse_headers(self.fp)

        # don't let the msg keep an fp
        self.msg.fp = None

        # are we using the chunked-style of transfer encoding?
        tr_enc = self.msg.get("transfer-encoding")
        if tr_enc and tr_enc.lower() == "chunked":
            self.chunked = 1
            self.chunk_left = None
        else:
            self.chunked = 0

        # will the connection close at the end of the response?
        self.will_close = self._check_close()

        # do we have a Content-Length?
        # NOTE: RFC 2616, S4.4, #3 says we ignore this if tr_enc is "chunked"
        length = self._get_content_length()
        if length is not None and length >= 0 and not self.chunked:
            self.length = length
        else:
            # Chunked, unknown or nonsensical (negative) length
            self.length = None

        # does the body have a fixed length? (of zero)
        if (
            status == NO_CONTENT
            or status == http.client.NOT_MODIFIED
            or 100 <= status < 200  # 1xx codes
            or self._method == "HEAD"
        ):
            self.length = 0

        # if the connection remains open, and we aren't using chunked, and
        # a content-length was not provided, then assume that the connection
        # WILL close.
        if not self.will_close and not self.chunked and self.length is None:
            self.will_close = 1

    def _get_content_length(self):
        """
        Some very strange sites will return two content-length headers. By
        default urllib2 will concatenate the two values using commas. Then
        when the value needs to be used... everything fails.

        This method tries to solve the issue by returning the lower value
        from the list. Sadly some bytes might be ignored, but it is much
        better than raising exceptions.

        :return: The content length (as integer), None when the header is
                 missing (most likely a chunked response) or invalid
        """
        length = self.msg.get("content-length")

        if length is None:
            return None

        try:
            return min(int(cl) for cl in length.split(","))
        except ValueError:
            return None

    def close(self):
        # First call parent's close()
        http.client.HTTPResponse.close(self)
        if self._handler:
            self._handler._request_closed(self._connection)

    def info(self):
        # pylint: disable=E1101
        return self.headers
        # pylint: enable=E1101

    def read(self, amt=None):
        """
        w3af reads the whole body at once and might read it many times, so
        the body is kept after the first read. When `amt` is given only the
        first `amt` bytes of the body are returned.
        """
        # TODO: Is this OK? What if a HEAD method actually returns something?!
        if self._method == "HEAD":
            # This indicates that we have read all that we needed from the socket
            # and that the socket can be reused!
            #
            # This like fixes the bug with title "GET is much faster than HEAD".
            # https://sourceforge.net/tracker2/?func=detail&aid=2202532&group_id=170274&atid=853652
            self.close()
            return b""

        if self._multiread is None:
            try:
                self._multiread = self._raw_read()
            except http.client.HTTPException:
                self.close()
                raise

        return self._multiread if amt is None else self._multiread[:amt]

    def set_body(self, data):
        """
        This was added to make my life a lot simpler while implementing mangle
        plugins
        """
        self._multiread = data

    def _check_close(self):
        """
        Overriding to add "max" support
        http://tools.ietf.org/id/draft-thomson-hybi-http-timeout-01.html#p-max
        """
        keep_alive = self.msg.get("keep-alive")

        if keep_alive and keep_alive.lower().endswith("max=1"):
            # We close right before the "max" deadline
            debug("will_close = True due to max=1")
            return True

        conn = self.msg.get("connection")

        # Is the remote end saying we need to keep the connection open?
        if conn and "keep-alive" in conn.lower():
            debug("will_close = False due to Connection: keep-alive")
            return False

        # Is the remote end saying we need to close the connection?
        elif conn and "close" in conn.lower():
            debug("will_close = True due to Connection: close")
            return True

        if self.version == 11:
            # An HTTP/1.1 connection is assumed to stay open unless explicitly
            # closed.
            debug("will_close = False due to default keep-alive in 1.1")
            return False

        # Proxy-Connection is a netscape hack.
        # otherwise, assume it will close
        pconn = self.msg.get("proxy-connection")
        return not (pconn and "keep-alive" in pconn.lower())
