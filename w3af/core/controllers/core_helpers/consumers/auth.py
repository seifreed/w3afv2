"""
auth.py

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

import logging
import queue

from w3af.core.constants import POISON_PILL
from w3af.core.controllers.profiling.took_helper import TookLine
from w3af.core.data.fuzzer.utils import rand_alnum

from .base_consumer import BaseConsumer, task_decorator
from .constants import FORCE_LOGIN

logger = logging.getLogger(__name__)


class auth(BaseConsumer):
    """
    Thread that logins into the application every N seconds.
    """

    def __init__(self, auth_plugins, w3af_core, timeout, output=None):
        """
        :param auth_plugins: Instances of auth plugins in a list
        :param w3af_core: The w3af core that we'll use for status reporting
        :param timeout: The time to wait between each login check
        """
        super().__init__(
            auth_plugins,
            w3af_core,
            thread_name=self.get_name(),
            create_pool=False,
            output=output,
        )

        self._timeout = timeout

    def get_name(self):
        return "Authenticator"

    def run(self):
        """
        Consume the queue items
        """
        while True:

            try:
                action = self.in_queue.get(timeout=self._timeout)
            except queue.Empty:
                self._login()
            else:

                if action == POISON_PILL:

                    try:
                        self._end_plugins()
                    finally:
                        self.in_queue.task_done()
                        self.set_has_finished()
                    break

                elif action == FORCE_LOGIN:
                    try:
                        self._login()
                    finally:
                        self.in_queue.task_done()

    def _end_plugins(self):
        for plugin in self._consumer_plugins:
            plugin.end()

    # Adding task here because we want to let the rest of the world know
    # that we're still doing something. The _task_done below will "undo"
    # this action.
    @task_decorator
    def _login(self, function_id):
        """
        This is the method that actually calls the plugins in order to login
        to the web application.
        """
        for plugin in self._consumer_plugins:

            debugging_id = rand_alnum(8)
            args = (plugin.get_name(), plugin.get_name(), debugging_id)
            msg = "auth consumer is calling %s.has_active_session() and %s.login() (did:%s)"

            self._output.debug(msg % args)

            took_line = TookLine(
                self._w3af_core, "auth", "_login", debugging_id=debugging_id
            )

            try:
                if not plugin.has_active_session(debugging_id=debugging_id):
                    plugin.login(debugging_id=debugging_id)
            except Exception as e:
                logger.debug("Unhandled exception in _login()", exc_info=True)
                self.handle_exception("auth", plugin.get_name(), None, e)

            took_line.send()

    def async_force_login(self):
        self.in_queue_put(FORCE_LOGIN)

    def force_login(self):
        self._login()
