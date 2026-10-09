"""
util.py

Copyright 2008 Andres Riancho

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


def mapDict(fun, dct):
    for p in dct:
        fun(p, dct[p])


def commonPrefix(completions):
    """
    Utility function which is used by console to extract the string to be
    suggested as autocompletion.
    :param completions: [(part, completion)] where part is a prefix of completion
    (see core.ui.console.menu)
    :author: Alexander Berezhnoy (alexander.berezhnoy |at| gmail.com)
    """

    def cp(str1, str2):
        """
        :return: the longest common prefix for 2 strings.
        """
        ls2 = len(str2)
        j = 1
        for i in range(len(str1)):
            if i >= ls2 or str1[i] != str2[i]:
                j = 0
                break

        result = str1[: i + j]
        return result

    # cut the prefix
    strs = [v[len(p) :] for (p, v) in completions]

    if len(strs) == 0:
        return ""

    if len(strs) == 1:
        return strs[0]

    result, tail = strs[0], strs[1:]
    for i in range(len(tail)):
        result = cp(result, tail[i])
        if result == "":
            break

    return result


def splitPath(path, sep="/"):
    """
    Chops the first part of a /-separated path and returns a tuple
    of the first part and the tail.
    If no separator in the path, the tail is None
    """
    sepIdx = path.find(sep)
    if sepIdx < 0:
        return (path, None)

    return path[:sepIdx], path[sepIdx + 1 :]


def suggest(tree, part, skipList=()):
    """
    The basic autocompletion logic.
    :param tree: dict of list to take possible completions from.
    @part: the prefix for the completions.
    @allowSet: if True, it allows to autocomplete expressions
    like "dog,!cat,gira" into dog,!cat,giraffee' (useful for plugins)
    :return: list of (p, c) where p is the prefix of the completion c and suffix of part.
        (currently, only lengths of p's are used).
    :author: Alexander Berezhnoy (alexander.berezhnoy |at| gmail.com)
    """
    lp = len(part)
    completions = [
        (part, v)
        for v in map(str, tree)
        if v.startswith(part) and v not in skipList and lp != len(v)
    ]

    suffix = " "

    if part in tree:
        completions.append((part, part + suffix))
    else:
        if len(completions) == 1:  # and not allowSet:
            theOption = completions[0]
            completions = [(theOption[0], theOption[1] + " ")]

    return completions
