from collections.abc import Buffer

def compress(
    data: str | Buffer,
    compression_level: int = 0,
    block_size: int = 0,
    content_checksum: bool = False,
    block_linked: bool = True,
    store_size: bool = True,
    return_bytearray: bool = False,
) -> bytes: ...
def decompress(
    data: str | Buffer,
    return_bytearray: bool = False,
    return_bytes_read: bool = False,
) -> bytes: ...
