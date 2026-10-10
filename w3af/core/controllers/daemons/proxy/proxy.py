"""
proxy.py

Copyright 2006 Andres Riancho

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

import asyncio
import os
import threading
from multiprocessing.dummy import Process

from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster

import w3af.core.controllers.output_manager as om
from w3af import ROOT_PATH
from w3af.core.controllers.daemons.proxy import ProxyHandler
from w3af.core.exceptions import ProxyException

STARTUP_FAILED = "Proxy server failed to start, the mitmproxy log has the details."


class Proxy(Process):
    """
    This class defines a simple HTTP proxy, it is mainly used for "complex"
    plugins.

    You should create a proxy instance like this:
        ws = Proxy('127.0.0.1', 8080, url_opener)

    Or like this, if you want to override the proxy handler (most times you
    want to do it!):
        ws = Proxy('127.0.0.1', 8080, url_opener, proxy_handler=ph)

    If the IP:Port is already in use, an exception will be raised while
    creating the ws instance.

    To start the proxy, and given that this is a Process class, you can do this:
        ws.start()

    Or if you don't want a different thread, you can simply call the run method:
        ws.run()

    The proxy handler class is the place where you'll perform all the magic
    stuff, like intercepting requests, modifying them, etc. A good idea if you
    want to code your own proxy handler is to inherit from the proxy handler
    that is already defined in this file (see: ProxyHandler).

    What you basically have to do is to inherit from it:
        class MyProxyHandler(ProxyHandler):

    And redefine the following methods:
        def do_ALL(self)
            Which originally receives a request from the browser, sends it to
            the remote site, receives the response and returns the response to
            the browser. This method is called every time the browser sends a
            new request.

    Things that work:
        - http requests like GET, HEAD, POST, CONNECT
        - https with certs and all (mitmproxy)

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    CA_CERT_DIR = os.path.join(ROOT_PATH, "core/controllers/daemons/proxy/ca/")

    def __init__(
        self,
        ip,
        port,
        uri_opener,
        handler_klass=ProxyHandler,
        ca_certs=CA_CERT_DIR,
        name="ProxyThread",
    ):
        """
        :param ip: IP address to bind
        :param port: Port to bind
        :param uri_opener: The uri_opener that will be used to open
                           the requests that arrive from the browser
        :param handler_klass: A class that will know how to handle
                              requests from the browser
        """
        Process.__init__(self)
        self.daemon = True
        self.name = name

        # Internal vars
        self._running = False
        self._uri_opener = uri_opener
        self._ca_certs = ca_certs
        self._host = ip
        self._requested_port = port
        self._port = port
        self._handler_klass = handler_klass
        self._ready = threading.Event()
        self._master = None
        self._handler = None

        # Stats
        self.total_handled_requests = 0

    def get_bind_ip(self):
        """
        :return: The IP address where the proxy will listen.
        """
        return self._host

    def get_bind_port(self):
        """
        :return: The TCP port where the proxy will listen.
        """
        return self._port

    def is_running(self):
        """
        :return: True if the proxy daemon is running
        """
        return self._running

    def get_port(self):
        return self._port

    def wait_for_start(self, timeout=30):
        if not self._ready.wait(timeout=timeout):
            raise ProxyException("Timed out while starting the proxy server.")
        if not self._running:
            raise ProxyException(STARTUP_FAILED)

    def _proxy_started(self, addresses):
        if addresses:
            self._port = addresses[0][1]
            self._ready.set()

    def run(self):
        """
        Starts the proxy daemon; usually this method isn't called directly. In
        most cases you'll call start()
        """

        async def start_master():
            proxy_options = options.Options(
                listen_host=self._host,
                listen_port=self._requested_port,
                confdir=self._ca_certs,
                ssl_insecure=True,
            )
            self._master = DumpMaster(
                proxy_options,
                with_termlog=False,
                with_dumper=False,
            )
            self._handler = self._handler_klass(self._master, self._uri_opener, self)
            self._master.addons.add(self._handler)
            args = (self._host, self._requested_port, self._handler.__class__.__name__)
            om.out.debug("Proxy server listening on {}:{} using {}".format(*args))
            self._running = True
            await self._master.run()

        try:
            asyncio.run(start_master())
        except SystemExit:
            # mitmproxy exits when it logs an error during startup, for
            # example when the address is already in use
            om.out.error(STARTUP_FAILED)
        finally:
            self._running = False
            self._ready.set()

    def stop(self):
        """
        Stop the proxy.
        """
        om.out.debug("Calling stop of proxy daemon")
        if self._running:
            self._master.shutdown()
