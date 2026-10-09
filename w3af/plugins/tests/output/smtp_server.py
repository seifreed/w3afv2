"""
smtp_server.py

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
"""

import socketserver
import threading
from dataclasses import dataclass, field


@dataclass
class ReceivedMail:
    from_address: str = ""
    to_addresses: list[str] = field(default_factory=list)
    message: str = ""


def _address_argument(line):
    return line.split(":", 1)[1].strip().strip("<>")


class SMTPRequestHandler(socketserver.StreamRequestHandler):
    """
    Speaks enough SMTP (RFC 5321) to receive the messages sent by smtplib.
    """

    server: "LocalSMTPServer"

    def handle(self):
        self._reply("220 localhost w3af test SMTP server")
        mail = ReceivedMail()

        for raw_line in self.rfile:
            line = raw_line.decode("utf-8").rstrip("\r\n")
            command = line[:4].upper()

            if command in ("HELO", "EHLO", "RSET", "NOOP"):
                self._reply("250 OK")
            elif command == "MAIL":
                mail = ReceivedMail(from_address=_address_argument(line))
                self._reply("250 OK")
            elif command == "RCPT":
                mail.to_addresses.append(_address_argument(line))
                self._reply("250 OK")
            elif command == "DATA":
                self._reply("354 End data with <CR><LF>.<CR><LF>")
                mail.message = self._read_data()
                self.server.inbox.append(mail)
                self._reply("250 OK")
            elif command == "QUIT":
                self._reply("221 Bye")
                return
            else:
                self._reply("502 Command not implemented")

    def _read_data(self):
        lines = []
        for raw_line in self.rfile:
            line = raw_line.decode("utf-8").rstrip("\r\n")
            if line == ".":
                break
            lines.append(line[1:] if line.startswith("..") else line)
        return "\n".join(lines)

    def _reply(self, text):
        self.wfile.write(f"{text}\r\n".encode())


class LocalSMTPServer(socketserver.ThreadingTCPServer):
    """
    A real SMTP server listening on an ephemeral 127.0.0.1 port which stores
    the received messages in its inbox.
    """

    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), SMTPRequestHandler)
        self.inbox: list[ReceivedMail] = []
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def port(self):
        return self.server_address[1]

    def start(self):
        self._thread.start()

    def stop(self):
        self.shutdown()
        self.server_close()
        self._thread.join()
