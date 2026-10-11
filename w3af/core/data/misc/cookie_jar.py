"""
cookie_jar.py

Copyright 2019 Andres Riancho

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

import re
import time
from http.cookiejar import Cookie, LoadError, MozillaCookieJar

# The header every Netscape cookie file starts with (http.cookiejar keeps its
# own copy of this regular expression private)
NETSCAPE_MAGIC_RE = re.compile("#( Netscape)? HTTP Cookie File", re.IGNORECASE)


class ImprovedMozillaCookieJar(MozillaCookieJar):
    def _really_load(self, f, filename, ignore_discard, ignore_expires):
        """
        Override this method in order to provide better error handling.
        """
        now = int(time.time())

        magic = f.readline()
        if not NETSCAPE_MAGIC_RE.search(magic):
            f.close()

            msg = "%r does not look like a Netscape format cookies file"
            raise LoadError(msg % filename)

        try:
            while 1:
                line = f.readline()
                if line == "":
                    break

                # last field may be absent, so keep any trailing tab
                line = line.removesuffix("\n")

                # skip comments and blank lines XXX what is $ for?
                if line.strip().startswith(("#", "$")) or line.strip() == "":
                    continue

                split_values = line.split("\t")

                if len(split_values) != 7:
                    msg = "Expected seven tab delimited fields, got %s in %s: %s"
                    error_args = (len(split_values), filename, line)
                    raise LoadError(msg % error_args)

                domain, domain_specified, path, secure, expires, name, value = (
                    split_values
                )

                secure = secure == "TRUE"
                domain_specified = domain_specified == "TRUE"
                if name == "":
                    # cookies.txt regards 'Set-Cookie: foo' as a cookie
                    # with no name, whereas cookielib regards it as a
                    # cookie with no value.
                    name = value
                    value = None

                initial_dot = domain.startswith(".")

                if domain_specified != initial_dot:
                    if domain_specified:
                        msg = (
                            "The second tab delimited field (domain_specified) is"
                            " set to %s and the domain does NOT start with a dot (%s)."
                            " This is not acceptable by the Mozilla Cookie format."
                            " Issue found at %s: %s"
                        )
                        domain_error_args = (domain_specified, domain, filename, line)
                        raise LoadError(msg % domain_error_args)

                    else:
                        msg = (
                            "The second tab delimited field (domain_specified) is"
                            " set to %s and the domain starts with a dot (%s)."
                            " This is not acceptable by the Mozilla Cookie format."
                            " Issue found at %s: %s"
                        )
                        domain_error_args = (domain_specified, domain, filename, line)
                        raise LoadError(msg % domain_error_args)

                discard = False
                if expires == "":
                    expires = None
                    discard = True
                else:
                    expires = int(expires)

                # assume path_specified is false
                c = Cookie(
                    0,
                    name,
                    value,
                    None,
                    False,
                    domain,
                    domain_specified,
                    initial_dot,
                    path,
                    False,
                    secure,
                    expires,
                    discard,
                    None,
                    None,
                    {},
                )
                if not ignore_discard and c.discard:
                    continue
                if not ignore_expires and c.is_expired(now):
                    continue
                self.set_cookie(c)

        except OSError:
            raise
        except Exception as e:
            raise LoadError(
                f"invalid Netscape format cookies file {filename!r}: {line!r}"
            ) from e
