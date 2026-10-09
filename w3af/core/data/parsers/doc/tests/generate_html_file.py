#!/usr/bin/env python
import sys

SOME_TEXT = "This is placeholder text"
OUTPUT_FILE = "w3af/core/data/parsers/doc/tests/data/huge.html"


def main():
    """
    Generate a huge HTML file which is useful for testing parser performance,
    not really real-life data, but forces the parser to use a lot of memory
    if it loads the whole thing right away/keeps the tree in memory.

    :return: None, we write the file to data/huge.html
    """
    output = open(OUTPUT_FILE, "w")
    write = lambda s: output.write(f"{s}\n")

    write("<html>")
    write(f"<title>{SOME_TEXT}</title>")

    write("<body>")

    #
    #   Long
    #
    for i in range(5000):
        write("<p>")
        write(SOME_TEXT)
        write("</p>")

        write("<p>")
        write(SOME_TEXT)
        write(f'<a href="/{i}">{SOME_TEXT}</a>')
        write("</p>")

        write("<div>")
        write(f'<a href="/{i}">{SOME_TEXT}</a>')
        write(SOME_TEXT)
        write(f'<form action="/{i}" method="POST">')
        write(f'<input type="text" name="abc-{i}">')
        write("</form>")
        write("</div>")

    #
    #   Long II
    #
    for i in range(5000):
        write("<div>")
        write(f'<img src="/img-{i}" />')
        write(f'<a href="mailto:andres{i}@test.com">{SOME_TEXT}</a>')
        write("</div>")

    #
    #   Deep
    #
    for i in range(5000):
        write(f'<div id="id-{i}">')
        write(f'<a href="/deep-div-{i}">{SOME_TEXT}</a>')

    for i in range(5000):
        write("<p>")
        write(SOME_TEXT)
        write("</p>")
        write("</div>")

    #
    #   Some scripts at the end
    #
    for i in range(50):
        write("<script><!-- code(); --></script>")

    write("</body>")
    write("</html>")


if __name__ == "__main__":
    sys.exit(main())
