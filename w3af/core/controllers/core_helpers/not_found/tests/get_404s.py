import http.client
import os
import shelve
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ALEXA_TOP1M = "http://s3.amazonaws.com/alexa-static/top-1m.csv.zip"
ALEXA_FILE = "top-1m.csv"
ALEXA_FILE_COMPRESSED = "top-1m.csv.zip"

if __name__ == "__main__":
    if not os.path.exists(ALEXA_FILE_COMPRESSED):
        resp = urllib.request.urlopen(ALEXA_TOP1M)
        with open(ALEXA_FILE_COMPRESSED, "wb") as compressed_file:
            compressed_file.write(resp.read())

    if not os.path.exists(ALEXA_FILE):
        with zipfile.ZipFile(ALEXA_FILE_COMPRESSED) as zfile:
            zfile.extract(ALEXA_FILE, ".")

    with shelve.open("data.shelve") as s, open(ALEXA_FILE) as alexa_file:
        # This is a "resume" feature
        last = len(s)
        print(f"c({last})", end=" ")

        for i, line in enumerate(alexa_file):
            if i <= last:
                continue

            line = line.strip()
            _, domain = line.split(",")

            try:
                ok = urllib.request.urlopen(f"http://{domain}/").read()
                try:
                    bad = urllib.request.urlopen(
                        f"http://{domain}/not-ex1st.html"
                    ).read()
                except urllib.error.HTTPError as error:
                    bad = error.read()
            except KeyboardInterrupt:
                break
            except urllib.error.HTTPError:
                sys.stdout.write("4")
                sys.stdout.flush()
            except (OSError, http.client.HTTPException):
                sys.stdout.write("E")
                sys.stdout.flush()
            else:
                s[domain] = (ok, bad)
                sys.stdout.write(".")
                sys.stdout.flush()

    sys.stdout.write("\n")
