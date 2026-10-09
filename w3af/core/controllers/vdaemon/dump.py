if __name__ == "__main__":
    import sys

    res = "file_dump = '"

    with open(sys.argv[1]) as dump_file:
        for i in dump_file.read():
            res += "\\x" + hex(ord(i))[2:].zfill(2)

    res += "'"
    print(res)
