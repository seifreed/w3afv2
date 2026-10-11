"""
master.py

Copyright 2015 Andres Riancho

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

# TODO: This is just a mock which in the future will allow us to have multiple
#       running scans at the same time, results for each, etc. Now we'll only
#       store one scan
#
# Store integer IDs as keys and active ScanInfo instances as values.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from w3af.core.controllers.w3af_core import w3afCore
    from w3af.core.ui.api.utils.log_handler import RESTAPIOutput


SCANS: dict[int, "ScanInfo | None"] = {}


class ScanInfo:
    def __init__(self):
        self.w3af_core: w3afCore | None = None
        self.output: RESTAPIOutput | None = None
        self.exception: Exception | None = None
        self.finished = False
        self.target_urls: list[str] | None = None
        self.profile_path: str | None = None

    def cleanup(self):
        w3af_core = self.w3af_core
        if w3af_core is not None:
            w3af_core.cleanup()
            w3af_core.quit()
            self.w3af_core = None

        output = self.output
        if output is not None:
            output.cleanup()
            self.output = None
