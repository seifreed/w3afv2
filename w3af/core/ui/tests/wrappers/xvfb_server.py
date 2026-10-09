"""
xvfb_server.py

Copyright 2011 Andres Riancho

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

import contextlib
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from typing import ClassVar

from w3af.core.ui.tests.wrappers.constants import DISPLAY
from w3af.core.ui.tests.wrappers.utils import restore_original_display


class XVFBServer(threading.Thread):
    """
    This class is a wrapper that helps me start/stop a Xvfb server and allows
    me to run any X client in it.

    For running LDTP tests we need to run Gnome (which actually provides the a11y
    features). Gnome is started once the Xvfb is ready and all the Gnome stuff
    is handled in gnome.py
    """

    WIDTH = 1024
    HEIGTH = 768

    REQUIRED_BINS: ClassVar[list[str]] = ["convert", "xvnc4viewer", "Xvfb", "x11vnc"]

    XVFB_BIN = "/usr/bin/Xvfb"
    START_CMD = f"{XVFB_BIN} {DISPLAY} -screen 0 {WIDTH}x{HEIGTH}x16 -fbdir {tempfile.gettempdir()}"

    SCREEN_XWD_FILE_0 = f"{tempfile.gettempdir()}/Xvfb_screen0"

    def __init__(self):
        super().__init__()
        self.name = "XVFBServer"
        self.daemon = True

        self.xvfb_process = None
        self.xvfb_start_result = None
        self.vnc_server_running = False

        self.verify_required_bins()

    def verify_required_bins(self):
        for binary in self.REQUIRED_BINS:
            status, _ = subprocess.getstatusoutput(f"which {binary}")
            if status != 0:
                raise RuntimeError(f'Missing binary requirement "{binary}".')

    def is_installed(self):
        status, output = subprocess.getstatusoutput(f"{self.XVFB_BIN} --fake")

        return bool(status == 256 and "use: X [:<display>] [option]" in output)

    def start_sync(self):
        """Launch the xvfb process and wait for it to start the X server

        :return: True if the server is started.
        """
        i = 0
        self.start()

        while i < 10:
            if self.xvfb_start_result is None:
                time.sleep(0.2)
                i += 1
            else:
                return self.xvfb_start_result

    def run(self):
        if self.is_installed():
            args = shlex.split(self.START_CMD)
            self.xvfb_process = subprocess.Popen(
                args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            # pylint: disable=E1101
            # E1101: Instance of 'Popen' has no 'wait' member
            returncode = self.xvfb_process.wait()

            if returncode != 0:
                self.xvfb_process = None
                self.xvfb_start_result = False

            self.xvfb_start_result = True

        self.xvfb_start_result = False

    def stop(self):
        if self.is_running():
            # pylint: disable=E1101
            # E1101: Instance of 'Popen' has no 'terminate' member
            self.xvfb_process.terminate()
            self.xvfb_process = None

        return True

    def is_running(self):
        return self.xvfb_process is not None

    def __del__(self):
        """Just in case, restore the DISPLAY to the original value again"""
        with contextlib.suppress(OSError):
            self.stop()
            restore_original_display()

    def run_x_process(self, cmd, block=False, display=DISPLAY):
        """
        Run a new process (in most cases one that will open an X window) within
        the xvfb instance.

        :param cmd: The command to run.
        :param block: If block is True this method blocks until the command
                      finishes, if not, the method returns immediately which
                      might lead to issues because of windows not being ready
                      yet inside the xvfb and checks being run on them.
        :return: True if the process was run. Please note that the method will
                 return True for commands that do not exist, fail, etc.
        """
        if not self.is_running():
            return False

        display_cmd = f"DISPLAY={display} {cmd}"

        if block:
            subprocess.getoutput(display_cmd)
        else:
            args = (display_cmd,)
            th = threading.Thread(target=subprocess.getoutput, args=args)
            th.daemon = True
            th.name = "XvfbProcess"
            th.start()

        return True

    def get_screenshot(self):
        """
        Verify useful for debugging! When a test does NOT pass we can take a
        screenshot of the current virtual X environment and "attach" it to the error
        log.

        Note: This requires Xvfb to be started with -fbdir
        """
        output_fname = None

        if self.is_running():

            for xwd_file in (self.SCREEN_XWD_FILE_0,):
                temp_file = tempfile.mkstemp(prefix="xvfb-screenshot-")[1]
                shutil.copy(xwd_file, temp_file)
                target_jpeg = temp_file + ".jpeg"
                convert_cmd = f"convert {temp_file} {target_jpeg}"
                _, _ = subprocess.getstatusoutput(convert_cmd)

                os.unlink(temp_file)

                output_fname = target_jpeg

        return output_fname

    def start_vnc_server(self):
        """
        Starts a VNC server that will show what's being displayed in our Xvfb
        (magic++).
        """
        if self.is_running():
            args = (f"x11vnc -display {DISPLAY} -shared -forever",)
            th = threading.Thread(target=subprocess.getoutput, args=args)
            th.daemon = True
            th.name = "VNCServer"
            th.start()
            self.vnc_server_running = True
            return True

    def start_vnc_client(self):
        """
        Requires "sudo apt-get install xvnc4viewer"
        """
        if not self.vnc_server_running:
            self.start_vnc_server()
            time.sleep(3)

        args = ("DISPLAY=:0 xvnc4viewer localhost",)
        th = threading.Thread(target=subprocess.getoutput, args=args)
        th.daemon = True
        th.name = "VNCClient"
        th.start()
