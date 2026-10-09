"""
Based heavily on code from:
    https://code.google.com/p/ssl-sni/source/browse/ssl_sni/openssl.py

Which uses the GNU Affero General Public License >= 3 , but that code is
actually based heavily on code from:
    https://github.com/t-8ch/requests/blob/d7908a9fdef7bca16e384ca42478d69d1894c8b6/requests/packages/urllib3/contrib/pyopenssl.py

Which is actually part of the "requests" project that's released under Apache
License, Version 2.0.

IANAL but I believe that the guys from ssl-sni made a mistake at changing the
license (basically they can't). So I'm choosing to use the original Apache
License, Version 2.0 for this file.
"""

import errno
import io
import select
import socket
import ssl
import time

import OpenSSL
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
from OpenSSL.SSL import SysCallError

CERT_NONE = ssl.CERT_NONE
CERT_OPTIONAL = ssl.CERT_OPTIONAL
CERT_REQUIRED = ssl.CERT_REQUIRED

_openssl_cert_reqs = {
    CERT_NONE: OpenSSL.SSL.VERIFY_NONE,
    CERT_OPTIONAL: OpenSSL.SSL.VERIFY_PEER,
    CERT_REQUIRED: OpenSSL.SSL.VERIFY_PEER | OpenSSL.SSL.VERIFY_FAIL_IF_NO_PEER_CERT,
}

NOT_AFTER_FORMAT = "%Y%m%d%H%M%SZ"


class _SSLConnectionIO(io.RawIOBase):
    """
    Raw binary reader over an SSLSocket, used by SSLSocket.makefile()
    """

    def __init__(self, ssl_socket):
        super().__init__()
        self.ssl_socket = ssl_socket

    def readable(self):
        return True

    def readinto(self, buffer):
        data = self.ssl_socket.recv(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def close(self):
        if not self.closed:
            try:
                super().close()
            finally:
                self.ssl_socket.close()


def _peer_already_closed(ssl_error):
    """
    :return: True when shutting down the TLS connection failed because the
             remote end already closed it: either the close_notify write hit
             a closed socket (EPIPE) or OpenSSL failed without any error in
             its queue after reading the remote EOF.
    """
    if isinstance(ssl_error, SysCallError):
        return ssl_error.args[:1] == (errno.EPIPE,)
    return ssl_error.args == ([],)


class SSLSocket:
    """
    This class was required to avoid the issue of "Bad file descriptor" which
    is generated when the remote server returns a connection: close header,
    which will trigger a self.close() in httplib's:

    def getresponse(self, buffering=False):
        ...
        if response.will_close:
            # this effectively passes the connection to the response
            self.close()

    Calling that self.close() will close the openssl connection, which we then
    read() to retrieve the http response body.

    Connection is not yet a new-style class, so I'm making a proxy instead of
    subclassing. Inspiration for this class comes from certmaster's source code

    Another reason for this wrapper is to implement timeouts for recv() and sendall()
    which require some ugly calls to select.select() because of pyopenssl limitations [2]

    [0] https://github.com/andresriancho/w3af/issues/8125
    [1] https://github.com/mpdehaan/certmaster/blob/master/certmaster/SSLConnection.py
    [2] https://github.com/andresriancho/w3af/issues/7989
    """

    def __init__(self, ssl_connection, sock):
        """
        :param ssl_connection: The established openssl connection
        :param sock: The underlying tcp/ip connection
        """
        self.ssl_conn = ssl_connection
        self.sock = sock
        self.close_refcount = 1
        self.closed = False

    def __getattr__(self, name):
        """
        Pass any un-handled function calls on to the connection, which in turn
        passes the ones it doesn't know about to the socket
        """
        return getattr(self.ssl_conn, name)

    def makefile(self, mode="rb"):
        """
        Keep the TLS connection alive until the response file and socket close.

        http.client only reads responses through binary buffered files, which
        is the only mode supported here.
        """
        if mode != "rb":
            raise ValueError(f'Unsupported mode "{mode}", only "rb" is supported')

        self.close_refcount += 1
        return io.BufferedReader(_SSLConnectionIO(self))

    def close(self):
        if self.closed:
            return

        self.close_refcount -= 1
        if self.close_refcount == 0:

            try:
                self.shutdown()
            except OpenSSL.SSL.Error as ssl_error:
                # The connection is already gone, which is what we wanted
                if not _peer_already_closed(ssl_error):
                    raise

            # Close doesn't seem to mind if the remote end already closed the
            # connection
            self.ssl_conn.close()
            self.closed = True

    def recv(self, *args, **kwargs):
        try:
            return self.ssl_conn.recv(*args, **kwargs)
        except (OpenSSL.SSL.ZeroReturnError, SysCallError):
            # empty bytes signal that the other side has closed the connection
            # or that some kind of error happen and no more reads should be
            # done on this socket
            return b""
        except OpenSSL.SSL.WantReadError:
            rd, _wd, _ed = select.select([self.sock], [], [], self.sock.gettimeout())
            if not rd:
                # The read timed out: report it as a closed connection
                return b""
            return self.recv(*args, **kwargs)

    def settimeout(self, timeout):
        return self.sock.settimeout(timeout)

    def _send_until_done(self, data):
        while True:
            try:
                return self.ssl_conn.send(data)
            except OpenSSL.SSL.WantWriteError:
                _, wlist, _ = select.select([], [self.sock], [], self.sock.gettimeout())
                if not wlist:
                    raise TimeoutError()

    def sendall(self, data):
        while len(data):
            sent = self._send_until_done(data)
            data = data[sent:]

    def getpeercert(self, binary_form=False):
        """
        :return: The remote peer certificate, as a dict similar to the one
                 returned by ssl.SSLSocket.getpeercert(), or as DER bytes when
                 binary_form is True
        """
        cert = self.ssl_conn.get_peer_certificate(as_cryptography=True)
        if cert is None:
            raise ssl.SSLError("No peer certificate")

        if binary_form:
            return cert.public_bytes(Encoding.DER)

        try:
            san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        except x509.ExtensionNotFound:
            dns_names = []
        else:
            dns_names = [
                ("DNS", name) for name in san.value.get_values_for_type(x509.DNSName)
            ]

        common_names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        common_name = common_names[0].value if common_names else None

        return {
            "subject": ((("commonName", common_name),),),
            "subjectAltName": dns_names,
            "notAfter": cert.not_valid_after_utc.strftime(NOT_AFTER_FORMAT),
        }


class OpenSSLReformattedError(Exception):
    def __init__(self, e):
        self.e = e

    def __str__(self):
        try:
            return f"*:{self.e.args[0][0][1]}:{self.e.args[0][0][2]} (glob)"
        except (IndexError, KeyError, TypeError):
            return str(self.e)


def wrap_socket(
    sock,
    cert_reqs=CERT_NONE,
    ssl_version=OpenSSL.SSL.TLSv1_1_METHOD,
    ca_certs=None,
    server_hostname=None,
    timeout=None,
):
    """
    Make a classic socket SSL aware

    :param sock: The classic TCP/IP socket
    :param timeout: Seconds to wait for the handshake and for each later read
                    or write. socket._GLOBAL_DEFAULT_TIMEOUT means the global
                    socket default, None means no timeout.
    :return: An SSLSocket instance
    """
    if timeout is socket._GLOBAL_DEFAULT_TIMEOUT:
        timeout = socket.getdefaulttimeout()

    cert_reqs = _openssl_cert_reqs[cert_reqs]

    ctx = OpenSSL.SSL.Context(ssl_version)

    if cert_reqs != OpenSSL.SSL.VERIFY_NONE:
        ctx.set_verify(cert_reqs, lambda a, b, err_no, c, d: err_no == 0)

    if ca_certs:
        try:
            ctx.load_verify_locations(ca_certs, None)
        except OpenSSL.SSL.Error as e:
            raise ssl.SSLError(f"Bad ca_certs: {ca_certs!r}", e)

    cnx = OpenSSL.SSL.Connection(ctx, sock)

    # SNI support
    if server_hostname is not None:
        cnx.set_tlsext_host_name(server_hostname.encode("idna"))

    cnx.set_connect_state()

    # SSL connection timeout doesn't work #7989 , so I'm not able to call:
    #   ctx.set_timeout(timeout)
    #
    # The workaround I found was to use select.select and non-blocking sockets,
    # and was implemented in SSLSocket (see above).
    #
    # Note that by setting the "sock" instance timeout, I'm also enforcing the
    # SSL connection timeout because of the fourth parameter sent to
    # select.select() in recv() and sendall().
    #
    # More information at:
    #    https://github.com/andresriancho/w3af/issues/7989
    sock.settimeout(timeout)
    time_begin = time.time()

    while True:
        try:
            cnx.do_handshake()
            break
        except OpenSSL.SSL.WantReadError:
            in_fds, _out_fds, _err_fds = select.select([sock], [], [], timeout)
            handshake_time = time.time() - time_begin
            if not in_fds or (timeout is not None and handshake_time > timeout):
                raise ssl.SSLError("do_handshake timed out")
        except SysCallError as e:
            raise ssl.SSLError(e.args)

    ssl_socket = SSLSocket(cnx, sock)
    ssl_socket.settimeout(timeout)

    return ssl_socket
