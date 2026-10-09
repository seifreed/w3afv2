"""
BaseFrameworkException.py

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

#
#   New to this code? Take a look at the exceptions documentation!
#   https://github.com/andresriancho/w3af/wiki/HTTP-error-handling-in-w3af
#

from w3af.core.exceptions import BaseFrameworkException


class RunOnce(Exception):
    """
    A small class that defines an exception to be raised by plugins that
    run only once and then are useless
    """

    def __init__(self, value=""):
        Exception.__init__(self)
        self.value = str(value)

    def __str__(self):
        return self.value


class NoMoreCalls(RunOnce):
    """
    A small class that defines an exception to be raised by plugins that
    don't want to be run anymore.
    """


class ProxyException(BaseFrameworkException):
    """
    A small class that defines a w3af Proxy Exception.
    """


class NoVulnerabilityFoundException(BaseFrameworkException):
    pass


class ExploitFailedException(BaseFrameworkException):
    pass


class FourOhFourDetectionException(BaseFrameworkException):
    pass
