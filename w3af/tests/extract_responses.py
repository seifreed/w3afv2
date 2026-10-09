import sys

USAGE = """\
python extract_responses.py <log-file> <response-id> [<response-id>]
"""


def read_response(filename, _id):
    recording = False
    output = ""

    with open(filename) as log_file:
        for line in log_file:
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
        with open(f"response-{_id}.txt", "w") as response_file:
            response_file.write(response)
