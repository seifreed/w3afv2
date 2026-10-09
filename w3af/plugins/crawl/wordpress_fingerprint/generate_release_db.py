"""
generate_release_db.py

Copyright 2012 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

"""
Utility to HTTP GET from wordpress.org and generate a DB with the archives/md5sums
"""
import re
import urllib.error
import urllib.parse
import urllib.request

release_re = r" \(<a href='https://wordpress.org/wordpress-(.*?).md5'>md5</a>"
release_md5_fmt = "https://wordpress.org/wordpress-%s.md5"

response = urllib.request.urlopen("https://wordpress.org/download/release-archive/")
extracted_links = re.findall(release_re, response.read())

if len(extracted_links) < 500:
    print("Error, extracted less than 500 links from the release archive URL.")

DEBUG = 0
errors = 0
counter = 0

with open("release.db", "w") as release_db:
    for i, version in enumerate(extracted_links):
        version_md5_url = release_md5_fmt % version
        try:
            version_md5 = urllib.request.urlopen(version_md5_url).read().strip()
        except KeyboardInterrupt:
            break
        except OSError:
            errors += 1
            if DEBUG:
                print(f"{version_md5_url} is a 404")
        else:
            if i % 15 == 0:
                print(f"[{i}/{len(extracted_links)}] {version_md5} {version}")
            release_db.write(f"{version_md5},{version}\n")

        if errors > 10:
            print("Found too many errors. Potential scrapping error. Stopping.")
            break
    else:
        print("Success.")
