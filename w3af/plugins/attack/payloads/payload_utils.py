"""Shared helpers for payload implementations."""

import ipaddress
import re


def parse_proc_net(data: str) -> list[list[str]]:
    """Split a Linux proc-net table into non-empty fields."""
    lines = [line for line in data.split("\n") if line]
    return [[field for field in line.split(" ") if field] for line in lines]


def get_process_username(passwd_data: str, user_id: str) -> str:
    """Return the account name matching a Linux process UID."""
    match = re.search(r"(\w*):(\w*):\d*:" + user_id, passwd_data, re.MULTILINE)
    return match.group(1) if match else ""


def split_proc_net_address(address: str) -> list[str]:
    """Split a Linux proc-net hexadecimal address into address and port."""
    return [address[:8], address[9:]]


def int_to_dotted_quad(value: int) -> str:
    """Convert an IPv4 integer to its dotted-quad representation."""
    return str(ipaddress.IPv4Address(value))
