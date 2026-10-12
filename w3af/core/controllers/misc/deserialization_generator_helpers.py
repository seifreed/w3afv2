"""Shared helpers for deserialization payload generators."""

import difflib


def find_payload_offsets(payload_bin_1, payload_bin_2, sample_1, sample_2, command_len):
    """Find command offsets shared by two payloads with equal command length."""
    offsets = []

    for a_index, b_index, size in difflib.SequenceMatcher(
        None, payload_bin_1, payload_bin_2
    ).get_matching_blocks():
        if size == 0:
            break

        bytes_at_p1 = payload_bin_1[a_index + size : a_index + size + command_len]
        bytes_at_p2 = payload_bin_2[b_index + size : b_index + size + command_len]

        if bytes_at_p1 == sample_1 and bytes_at_p2 == sample_2:
            offsets.append(a_index + size)

    return offsets
