"""
auto_update.py

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

import os

import git

from w3af.core.controllers.auto_update.git_client import GitClientError
from w3af.core.controllers.auto_update.utils import is_git_repo
from w3af.core.controllers.auto_update.version_manager import VersionMgr
from w3af.core.controllers.misc.home_dir import W3AF_LOCAL_PATH, verify_dir_has_perm


class UIUpdater:
    """
    Base class that provides an API for UI update workers.
    """

    def __init__(self, force=False, ask=None, logger=None):
        self._force_upd = force
        self._ask = ask
        self._logger = logger
        self._callbacks = {"callback_onupdate_confirm": ask}
        self._registries = {}

    @property
    def _vmngr(self):
        vmngr = getattr(self, "__vmngr", None)
        if vmngr is None:
            vmngr = VersionMgr(log=self._logger)
            for name, callback in self._callbacks.items():
                setattr(vmngr, name, callback)
            for event, (func, message) in self._registries.items():
                vmngr.register(event, func, message)
            setattr(self, "__vmngr", vmngr)
        return vmngr

    def _add_callback(self, callback_name, callback):
        self._callbacks[callback_name] = callback

    def _register(self, event, func, msg):
        self._registries[event] = (func, msg)

    def update(self):
        if (
            self._force_upd in (None, True)
            and is_git_repo()
            and verify_dir_has_perm(W3AF_LOCAL_PATH, os.W_OK, levels=1)
        ):
            try:
                resp = self._call_update()
                self._handle_update_output(resp)
            except KeyboardInterrupt:
                pass
            except (GitClientError, git.exc.GitError, OSError) as ex:
                self._logger(f'An error occurred while updating: "{ex}"')

    def _call_update(self):
        return self._vmngr.update(self._force_upd)

    def _handle_update_output(self, resp):
        raise NotImplementedError("Must be implemented by subclass")

    def _log(self, msg):
        print(msg)
