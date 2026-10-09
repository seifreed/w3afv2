"""
update_scan_db.py

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

import sys

import requests

scan_db_url = "https://raw.github.com/sullo/nikto/master/program/databases/db_tests"
target_path = "scan_database.db"
DOWNLOAD_TIMEOUT = 60

response = requests.get(scan_db_url, timeout=DOWNLOAD_TIMEOUT)
response.raise_for_status()
db_content = response.text

if "Source: https://cirt.net" not in db_content:
    print("db_tests download failed")
    sys.exit(-1)

with open(target_path, "w") as target_fd:
    target_fd.write(db_content)
