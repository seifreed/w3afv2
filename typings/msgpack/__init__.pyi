from typing import IO, Any

def packb(
    o: Any, *, use_bin_type: bool = True, use_single_float: bool = False
) -> bytes: ...
def unpackb(
    packed: bytes,
    *,
    raw: bool = False,
    use_list: bool = True,
    strict_map_key: bool = True,
) -> Any: ...
def pack(
    o: Any,
    stream: IO[bytes],
    *,
    use_bin_type: bool = True,
    use_single_float: bool = False,
) -> None: ...
def unpack(
    stream: IO[bytes],
    *,
    raw: bool = False,
    use_list: bool = True,
    strict_map_key: bool = True,
) -> Any: ...

dumps = packb
loads = unpackb
dump = pack
load = unpack
