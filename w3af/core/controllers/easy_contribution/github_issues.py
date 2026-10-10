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
import time

from github import Auth, BadCredentialsException, Github, GithubException

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

GITHUB_API_URL = "https://api.github.com"
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


class LoginFailed(Exception):
    pass


class NotLoggedIn(Exception):
    pass


class GithubIssues:
    def __init__(self, token, base_url=GITHUB_API_URL):
        self._token = token
        self._base_url = base_url
        self.gh = None

    def login(self):
        self.gh = Github(auth=Auth.Token(self._token), base_url=self._base_url)

        # This is just a small piece of code which sends a request to the
        # API in order to verify if the token is fine. Doesn't really do
        # anything with the user credentials.
        try:
            list(self.gh.get_user().get_repos())
        except BadCredentialsException:
            raise OAuthTokenInvalid("Invalid OAuth token")
        except (OSError, GithubException) as ex:
            raise LoginFailed(str(ex))

        return True

    def report_bug(
        self,
        summary,
        userdesc,
        tback="",
        plugins="",
        autogen=True,
        email=None,
    ):
        if self.gh is None:
            raise NotLoggedIn("Please login before reporting a bug.")

        summary, desc = self._build_summary_and_desc(
            summary, userdesc, tback, plugins, autogen, email
        )

        w3af_repo = self.gh.get_user("andresriancho").get_repo("w3af")

        # Github doesn't allow users that do NOT own the repository to assign
        # labels to new issues, so none are sent
        issue = w3af_repo.create_issue(title=summary, body=desc)
        return issue.number, TICKET_URL_FMT % issue.number

    def _build_summary_and_desc(self, summary, desc, tback, plugins, autogen, email):
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
                m.update(time.ctime().encode())
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
                "\n\nThe user provided the following email address for contact: %s"
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
