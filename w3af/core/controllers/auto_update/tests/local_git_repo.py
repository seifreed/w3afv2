"""
local_git_repo.py

Copyright 2026 w3af contributors

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

Throwaway git repositories for the auto_update tests. Every repository is
created below a caller-provided temporary directory, so the tests never read
from or write to the w3af working copy.
"""

import os

import git

BRANCH = "main"
AUTHOR = git.Actor("w3af tests", "tests@w3af.invalid")


def init_repo(path):
    """
    :return: A new git.Repo at path with BRANCH as its initial branch.
    """
    return git.Repo.init(path, initial_branch=BRANCH)


def write_file(repo, filename, content):
    with open(os.path.join(repo.working_tree_dir, filename), "w") as handle:
        handle.write(content)


def commit_file(repo, filename, content, message):
    """
    Writes content to filename, stages it and commits it.

    :return: The hexsha of the new commit.
    """
    write_file(repo, filename, content)
    repo.index.add([filename])
    return commit(repo, message)


def delete_file(repo, filename, message):
    """
    Removes filename from the repository and commits the deletion.

    :return: The hexsha of the new commit.
    """
    repo.index.remove([filename], working_tree=True)
    return commit(repo, message)


def commit(repo, message):
    new_commit = repo.index.commit(message, author=AUTHOR, committer=AUTHOR)
    return new_commit.hexsha


def clone_repo(upstream, path):
    """
    :return: A git.Repo cloned from upstream whose "origin" points to it.
    """
    return git.Repo.clone_from(upstream.working_tree_dir, path)


class CallRecorder:
    """
    Callable that records the positional arguments of every call and returns
    a fixed value.
    """

    def __init__(self, return_value=None):
        self.calls = []
        self._return_value = return_value

    def __call__(self, *args):
        self.calls.append(args)
        return self._return_value
