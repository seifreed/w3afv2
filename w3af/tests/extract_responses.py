import sys

USAGE = """\
python extract_responses.py <log-file> <response-id> [<response-id>]
"""


def read_response(filename, _id):
    recording = False
    output = ""

    for line in open(filename):
        if line.startswith("=" * 40 + f"Response {_id} "):
            recording = True
            continue

        if recording and line.startswith("=" * 80):
            break

        if recording:
            output += line

    return output


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(1)

    filename = sys.argv[1]
    ids = sys.argv[2:]

    for _id in ids:
        print(f"Processing response {_id}")
        response = read_response(filename, _id)
        open(f"response-{_id}.txt", "w").write(response)
