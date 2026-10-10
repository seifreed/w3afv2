"""
sqlmap_wrapper.py

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

import errno
import os
import re
import shlex
import sys
import tempfile
from importlib.resources import files

from w3af.core.controllers.daemons.proxy import Proxy
from w3af.core.controllers.misc.external_process import PIPE, start_process
from w3af.core.data.parsers.doc.url import URL

SQLMAP_SCRIPT = str(files("sqlmap") / "sqlmap.py")


class SQLMapWrapper:

    OUTPUT_DIR = os.path.join(tempfile.gettempdir(), str(os.getpid()))
    DEBUG_ARGS = ("-v6",)
    BASE_ARGS = (sys.executable, SQLMAP_SCRIPT, f"--output-dir={OUTPUT_DIR}")

    VULN_STR = "[INFO] the back-end DBMS is"
    NOT_VULN_STR = "all tested parameters do not appear to be injectable"

    SQLMAP_ERRORS = (
        "connection timed out to the target",
        "infinite redirect loop detected",
        "it is not recommended to continue in this kind of cases",
        "unable to connect to the target url or proxy",
        "[INFO] skipping '",
        "[CRITICAL] unable to retrieve page content",
        "establish SSL connection",
    )

    def __init__(self, target, uri_opener, output, coloring=False, debug=False):
        if not isinstance(target, Target):
            fmt = "Invalid type %s for target parameter in SQLMapWrapper ctor."
            raise TypeError(fmt % type(target))

        self.debug = debug
        self._output = output
        self.target = target
        self.coloring = coloring
        self.last_command = None
        self.verified_vulnerable = False
        self.proxy = None
        self.local_proxy_url = None
        self.last_stdout = None
        self.last_stderr = None

        if uri_opener is not None:
            self.start_proxy(uri_opener)

    def start_proxy(self, uri_opener):
        """
        Saves the proxy configuration to self.local_proxy_url in order for the
        wrapper to use it in the calls to sqlmap.py and have the traffic go
        through our proxy (which has the user configuration, logging, etc).

        :return: None, an exception is raised if something fails.
        """
        host = "127.0.0.1"

        self.proxy = Proxy(host, 0, uri_opener, name="SQLMapWrapperProxy")
        self.proxy.start()
        self.proxy.wait_for_start()

        self.local_proxy_url = f"http://{host}:{self.proxy.get_bind_port()}/"

    def __reduce__(self):
        """
        Need to define this method in order to remove the uri_opener from the
        pickled string. This will make sure that when the object is un-pickled
        we get the real uri_opener from w3af's core.

        The object being un-pickled is the SQLMapShell, which when un-pickled
        from the kb we call "shell.set_url_opener(w3af_core.uri_opener)",
        which then calls start_proxy(uri_opener) in order to restore the opener
        """
        return self.__class__, (
            self.target,
            None,
            self._output,
            self.coloring,
            self.debug,
        )

    def cleanup(self):
        self.proxy.stop()

    def is_vulnerable(self):
        """
        :return: True if the URL is vulnerable to SQL injection.
        """
        if self.verified_vulnerable:
            return self.verified_vulnerable

        params = ["--batch"]

        full_command, stdout, _stderr = self.run_sqlmap(params)

        if full_command is None:
            # Something really bad happen with sqlmap
            return False

        if self.VULN_STR in stdout and self.NOT_VULN_STR not in stdout:
            self.verified_vulnerable = True
            return True

        if self.NOT_VULN_STR in stdout and self.VULN_STR not in stdout:
            return False

        for error_string in self.SQLMAP_ERRORS:
            if error_string in stdout:
                # We found an unknown sqlmap error, such as a timeout
                return False

        fmt = 'Unexpected answer found in sqlmap output for command "%s": "%s"'
        raise NotImplementedError(fmt % (full_command, stdout))

    def _run(self, custom_params):
        """
        Internal function used by run_sqlmap and run_sqlmap_with_pipes to
        call subprocess.

        :return: A Popen object.
        """
        if not os.path.exists(self.OUTPUT_DIR):
            os.mkdir(self.OUTPUT_DIR)

        final_params = self.get_wrapper_params(custom_params)
        target_params = self.target.to_params()

        all_params = [*self.BASE_ARGS, *final_params, *target_params]

        if self.debug:
            all_params.extend(self.DEBUG_ARGS)

        try:
            process = start_process(
                all_params, stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True
            )
        except OSError as os_err:
            # https://github.com/andresriancho/w3af/issues/10186
            # OSError: [Errno 12] Cannot allocate memory
            if os_err.errno == errno.ENOMEM:
                msg = (
                    "The operating system is running low on memory and"
                    " failed to start the sqlmap process."
                )
                self._output.error(msg)

                # This tells the rest of the world that the command failed
                self.last_command = None
                return None
            else:
                # Let me discover/handle other errors
                raise

        else:
            full_command = " ".join(all_params)
            self.last_command = full_command
            return process

    def run_sqlmap(self, custom_params):
        """
        Run sqlmap and wait for it to finish before getting its output.

        :param custom_params: A list with the extra parameters that we want to
                              send to sqlmap.

        :return: Runs sqlmap and returns a tuple containing:
                    (last command run,
                     stdout,
                     stderr)
        """
        process = self._run(custom_params)

        # Error handling for sqlmap problems
        if process is None:
            return None, None, None

        self.last_stdout, self.last_stderr = process.communicate()

        self._output.debug(f"[sqlmap_wrapper] {self.last_command}")
        for line in self.last_stdout.split("\n"):
            self._output.debug(f"[sqlmap_wrapper] {line}")

        return self.last_command, self.last_stdout, self.last_stderr

    def run_sqlmap_with_pipes(self, custom_params):
        """
        Run sqlmap and immediately return handlers to stdout, stderr and stdin
        so the code using this can interact directly with the process.

        :param custom_params: A list with the extra parameters that we want to
                              send to sqlmap.

        :return: Runs sqlmap and returns a tuple with:
                    (last command run,
                     Popen object so that everyone can read .stdout)

                 This is very useful for using with w3af's output manager.
        """
        process = self._run(custom_params)

        # Error handling for sqlmap problems
        if process is None:
            return None, None

        return self.last_command, process

    def direct(self, params):

        if isinstance(params, str):
            extra_params = shlex.split(params)
        else:
            extra_params = params

        return self.run_sqlmap_with_pipes(extra_params)

    def get_wrapper_params(self, extra_params=None):
        # TODO: This one will disappear the day I add stdin handling support
        #       for the wrapper. Please remember that this support will have to
        #       take care of stdin and all other inputs from other UIs
        params = ["--batch"]

        if not self.coloring:
            params.append("--disable-coloring")

        if self.local_proxy_url is not None:
            params.append(f"--proxy={self.local_proxy_url}")

        if extra_params is not None:
            params.extend(extra_params)

        return params

    def _wrap_param(self, custom_params):
        """
        Utility function to allow me to easily wrap params.

        :return: Runs sqlmap with --dbs and returns a tuple with:
                    (last command run,
                     Popen object so that everyone can read .stdout,
                     .stderr, .stdin attributes)
        """
        process = self._run(custom_params)

        # Error handling for sqlmap problems
        if process is None:
            return None, None

        return self.last_command, process

    def dbs(self):
        return self._wrap_param(["--dbs"])

    def tables(self):
        return self._wrap_param(["--tables"])

    def users(self):
        return self._wrap_param(["--users"])

    def dump(self):
        return self._wrap_param(["--dump"])

    def read(self, filename):
        """
        :param filename: The file to be read
        :return: The contents of the file that was passed as parameter
        """
        _cmd, process = self._wrap_param([f"--file-read={filename}"])
        stdout = process.stdout.read()
        match = re.search("the local file '(.*?)' and", stdout)
        if match is None or not os.path.exists(match.group(1)):
            return ""

        with open(match.group(1)) as local_file:
            return local_file.read()


class Target:
    def __init__(self, uri, post_data=None):
        if not isinstance(uri, URL):
            fmt = "Invalid type %s for uri parameter in Target ctor."
            raise TypeError(fmt % type(uri))

        if post_data is not None and not isinstance(post_data, str):
            fmt = "Invalid type %s for post_data parameter in Target ctor."
            raise TypeError(fmt % type(post_data))

        self.uri = uri
        self.post_data = post_data

    def to_params(self):
        params = [f"--url={self.uri}"]

        if self.post_data is not None:
            params.append(f"--data={self.post_data}")

        return params

    def __repr__(self):
        return f"<Target {self.uri} {self.post_data}>"
