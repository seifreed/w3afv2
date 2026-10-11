"""SOCKS4 protocol values, errors, and request decoding."""

import ipaddress
import socket
import struct
from typing import TypedDict

UNSPECIFIED_IP = str(ipaddress.IPv4Address(0))

SOCKS_VERSION = 4

COMMAND_CONNECT = 1
COMMAND_BIND = 2
COMMANDS = [COMMAND_CONNECT, COMMAND_BIND]

REQUEST_GRANTED = 90
REQUEST_REJECTED_FAILED = 91
REQUEST_REJECTED_NO_IDENTD = 92
REQUEST_REJECTED_IDENT_FAILED = 93

ERR_CONNECTION_RESET_BY_PEER = 10054
ERR_CONNECTION_REFUSED = 10061


class FileError(Exception):
    pass


class SocksError(Exception):
    pass


class Connection_Closed(SocksError):
    pass


class Bind_TimeOut_Expired(SocksError):
    pass


class Request_Error(SocksError):
    pass


class Client_Connection_Closed(Connection_Closed):
    pass


class Remote_Connection_Closed(Connection_Closed):
    pass


class Remote_Connection_Failed(Connection_Closed):
    pass


class Remote_Connection_Failed_Invalid_Host(Remote_Connection_Failed):
    pass


class Request_Failed(Request_Error):
    pass


class Request_Failed_No_Identd(Request_Failed):
    pass


class Request_Failed_Ident_failed(Request_Failed):
    pass


class Request_Refused(Request_Error):
    pass


class Request_Bad_Version(Request_Refused):
    pass


class Request_Unknown_Command(Request_Refused):
    pass


class Request_Unauthorized_Client(Request_Refused):
    pass


class Request_Invalid_Port(Request_Refused):
    pass


class Request_Invalid_Format(Request_Refused):
    pass


class SocksRequest(TypedDict, total=False):
    version: int
    command: int
    address: tuple[str, int]
    userid: bytes


def is_port(port):
    return 0 < port < 65536


def string2port(port_str):
    """Convert a packed 16-bit port to an integer."""
    return struct.unpack(">H", port_str)[0]


def port2string(port):
    """Convert an integer port to its packed 16-bit representation."""
    return struct.pack(">H", port)


def decode_request(data: bytes) -> SocksRequest:
    """Decode and validate one SOCKS4 request frame."""
    if len(data) < 9:
        raise Request_Invalid_Format(data)

    request: SocksRequest = {
        "version": data[0],
        "command": data[1],
    }
    if request["version"] != SOCKS_VERSION:
        raise Request_Bad_Version(request)

    if request["command"] not in COMMANDS:
        raise Request_Unknown_Command(request)

    address = (socket.inet_ntoa(data[4:8]), string2port(data[2:4]))
    if not is_port(address[1]):
        raise Request_Invalid_Port(request)

    request["address"] = address
    request["userid"] = data[8:].strip(b"\x00")
    return request
