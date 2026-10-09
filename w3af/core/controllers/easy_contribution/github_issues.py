"""
github_issues.py

Copyright 2013 Andres Riancho

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

import hashlib
import os
import socket
import ssl
import time

from github import BadCredentialsException, Github, GithubException

from w3af.core.controllers.exception_handling.helpers import get_versions

DEFAULT_BUG_QUERY_TEXT = """What steps will reproduce the problem?
1.
2.
3.

What is the expected output? What do you see instead?


What operating system are you using?


Please provide any additional information below:


"""

OAUTH_AUTH_FAILED = """Failed to authenticate with github.com , please try\
 again later. If the authentication still fails it might be because the\
 current w3af version is outdated and is not allowed to report any new\
 issues."""

TICKET_URL_FMT = "https://github.com/andresriancho/w3af/issues/%s"

GITHUB_CREDENTIAL_ENV_VAR = "W3AF_GITHUB_OAUTH_TOKEN"
MISSING_CREDENTIAL_MSG = (
    f"Reporting bugs to GitHub requires a personal access token in the"
    f" {GITHUB_CREDENTIAL_ENV_VAR} environment variable."
)


def get_oauth_token():
    """
    :return: The GitHub token used to report bugs, or None when the user did
             not configure one.
    """
    return os.environ.get(GITHUB_CREDENTIAL_ENV_VAR) or None


class OAuthTokenInvalid(Exception):
    pass


class UserCredentialsInvalid(Exception):
    pass


class LoginFailed(Exception):
    pass


class NotLoggedIn(Exception):
    pass


class GithubIssues:
    def __init__(self, user_or_token, password=None):
        self._user_or_token = user_or_token
        self._password = password
        self.gh = None
        self.using_oauth = password is None

    def login(self):
        try:
            self.gh = Github(self._user_or_token, self._password)
        except GithubException as ex:
            # Not sure when we get here, but just in case...
            raise LoginFailed(str(ex))
        else:
            # This is just a small piece of code which sends a request to the
            # API in order to verify if the credentials are fine. Doesn't
            # really do anything with the user credentials.
            try:
                [i for i in self.gh.get_user().get_repos()]
            except BadCredentialsException:
                # The token and/or user provided credentials are incorrect
                if self.using_oauth:
                    raise OAuthTokenInvalid("Invalid OAuth token")
                else:
                    raise UserCredentialsInvalid("Invalid user credentials")
            except (TimeoutError, ssl.SSLError, GithubException, socket.gaierror) as ex:
                raise LoginFailed(str(ex))

        return True

    def report_bug(
        self,
        summary,
        userdesc,
        tback="",
        fname=None,
        plugins="",
        autogen=True,
        email=None,
    ):
        if self.gh is None:
            raise NotLoggedIn("Please login before reporting a bug.")

        summary, desc = self._build_summary_and_desc(
            summary, userdesc, tback, fname, plugins, autogen, email
        )

        w3af_repo = self.gh.get_user("andresriancho").get_repo("w3af")
        labels = []
        # Github doesn't allow users that do NOT own the repository to assign
        # labels to new issues
        # labels = [w3af_repo.get_label('automatic-bug-report'),
        #          w3af_repo.get_label('bug')]

        issue = w3af_repo.create_issue(title=summary, body=desc, labels=labels)
        return issue.number, TICKET_URL_FMT % issue.number

    def _build_summary_and_desc(
        self, summary, desc, tback, fname, plugins, autogen, email
    ):
        """
        Build the formatted summary and description that will be
        part of the reported bug.
        """
        #
        #    Define which summary to use
        #
        if summary:
            bug_summary = summary
        else:
            # Try to extract the last line from the traceback:
            if tback:
                bug_summary = tback.split("\n")[-2]
            else:
                # Failed... lets generate something random!
                m = hashlib.md5(usedforsecurity=False)
                m.update(time.ctime())
                bug_summary = m.hexdigest()

        # Generate the summary string. Concat 'user_title'
        summary = "{}Bug Report - {}".format(
            autogen and "[Auto-Generated] " or "",
            bug_summary,
        )

        if desc.strip() == DEFAULT_BUG_QUERY_TEXT.strip():
            desc = ""

        #
        # Define which description to use (depending on the availability of an
        # email provided by the user or not).
        #
        if email is not None:
            email_fmt = (
                "\n\nThe user provided the following email address for" "contact: %s"
            )
            desc += email_fmt % email

        # Build details string
        details = ""
        if desc:
            details += desc
            details += "\n"

        details += "## Version Information\n"
        details += "```\n"
        details += get_versions()
        details += "\n```\n"

        details += "## Traceback\n"
        details += "```pytb\n"
        details += tback
        details += "\n```\n"

        if plugins:
            details += "## Enabled Plugins\n"
            details += "```python\n"
            details += plugins
            details += "\n```\n"

        return summary, details
