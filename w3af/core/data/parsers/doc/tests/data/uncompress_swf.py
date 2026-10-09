import sys
import zlib
from pathlib import Path

if __name__ == "__main__":
    filename = Path(sys.argv[1])

    compressed_data = filename.read_bytes()[8:]
    uncompressed_data = zlib.decompress(compressed_data)

    filename.with_name(f"{filename.name}.bytecode").write_bytes(uncompressed_data)
