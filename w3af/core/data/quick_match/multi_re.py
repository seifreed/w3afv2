"""
multi_re.py

Copyright 2017 Andres Riancho

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
from collections.abc import Iterable

from multiregex import RegexMatcher

from w3af.core.data.constants.encodings import DEFAULT_ENCODING


class MultiRE:

    def __init__(self, regexes_or_assoc, re_compile_flags=0, hint_len=3):
        """
        :param re_compile_flags: The regular expression compilation flags

        :param hint_len: Use only hints larger than hint_len to speed-up the search.

        :param regexes_or_assoc: A list with all the regular expressions that
                                 we want to match against one or more strings
                                 using the "query" function.

                                This list might look like:
                                    [re_str_1, re_str_2 ... , re_str_N]

                                Or something like:
                                    [(re_str_1, obj1), ..., (re_str_N, objN)].

                                In the first case, if a match is found this class
                                will return:
                                    [(match_obj, re_str_N, compiled_regex),]

                                In the second case we'll return:
                                    [(match_obj, re_str_N, compiled_regex, objN),]
        """
        self._regexes_or_assoc = regexes_or_assoc
        self._re_compile_flags = re_compile_flags
        self._hint_len = hint_len
        self._translator = {}
        self._re_cache = {}
        self._regexes_with_no_keywords = []
        self._matcher_to_regexes = {}
        self._matcher = self._build()

    def _build(self):
        matcher_patterns = []

        for item in self._regexes_or_assoc:

            #
            #   First we compile all regular expressions and save them to
            #   the re_cache.
            #
            if isinstance(item, tuple):
                regex = item[0]
                self._re_cache[regex] = re.compile(regex, self._re_compile_flags)

                if regex in self._translator:
                    raise ValueError(f'Duplicated regex "{regex}"')

                self._translator[regex] = item[1:]
            elif isinstance(item, str):
                regex = item
                self._re_cache[regex] = re.compile(regex, self._re_compile_flags)
            else:
                raise TypeError("Can NOT build MultiRE with provided values.")

            matcher_regex = self._re_cache[regex]
            try:
                prematchers = RegexMatcher.generate_prematchers(matcher_regex)
            except ValueError:
                prematchers = set()
            prematchers = {
                prematcher
                for prematcher in prematchers
                if len(prematcher.encode(DEFAULT_ENCODING)) > self._hint_len
            }

            if not prematchers:
                self._regexes_with_no_keywords.append(regex)
            matcher_patterns.append((matcher_regex, prematchers))
            self._matcher_to_regexes.setdefault(matcher_regex, []).append(regex)

        if not any(prematchers for _, prematchers in matcher_patterns):
            return None
        return RegexMatcher(matcher_patterns)

    def query(self, target_str):
        """
        Run through all the regular expressions and identify them in target_str.

        We'll only run the regular expressions if:
             * They do not have keywords
             * The keywords exist in the string

        :param target_str: The target string where the keywords need to be match
        :yield: (match_obj, re_str_N, compiled_regex)
        """
        if isinstance(target_str, str):
            matcher_target = target_str
        else:
            matcher_target = target_str.decode(DEFAULT_ENCODING, "surrogateescape")

        regexes: Iterable[str]
        if self._matcher is None:
            regexes = self._re_cache
        else:
            candidate_patterns = self._matcher.get_pattern_candidates(matcher_target)
            candidate_counts: dict[str, int] = {}
            regexes = []
            for candidate_pattern in candidate_patterns:
                candidate_index = candidate_counts.get(candidate_pattern, 0)
                regexes.append(
                    self._matcher_to_regexes[candidate_pattern][candidate_index]
                )
                candidate_counts[candidate_pattern] = candidate_index + 1

        for regex in regexes:
            compiled_regex = self._re_cache[regex]
            matchobj = compiled_regex.search(matcher_target)
            if matchobj:
                yield self._create_output(matchobj, regex, compiled_regex)

    def _create_output(self, matchobj, regex, compiled_regex):
        extra_data = self._translator.get(regex, None)

        if extra_data is None:
            return matchobj, regex, compiled_regex
        else:
            all_data = [matchobj, regex, compiled_regex]
            all_data.extend(extra_data)
            return all_data
