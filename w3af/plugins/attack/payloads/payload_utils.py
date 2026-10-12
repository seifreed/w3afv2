"""Shared helpers for payload implementations."""

import ipaddress


def int_to_dotted_quad(value: int) -> str:
    """Convert an IPv4 integer to its dotted-quad representation."""
    return str(ipaddress.IPv4Address(value))
