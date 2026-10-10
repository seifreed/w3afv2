"""Persistence-independent Knowledge Base behavior."""

import copy
import logging
import threading

from w3af.core.data.kb.info import Info
from w3af.core.data.kb.info_set import InfoSet
from w3af.core.data.kb.shell import Shell
from w3af.core.data.kb.vuln import Vuln
from w3af.core.data.misc.lru import SynchronizedLRUDict

LOGGER = logging.getLogger(__name__)


class BasicKnowledgeBase:
    """
    This is a base class from which all implementations of KnowledgeBase will
    inherit. It has the basic utility methods that will be used.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    def __init__(self):
        self._kb_lock = threading.RLock()

        self.FILTERS = {"URL": self.filter_url, "VAR": self.filter_var}

        self._reached_max_info_instances_cache = SynchronizedLRUDict(512)

    def append_uniq(self, location_a, location_b, info_inst, filter_by="VAR"):
        """
        Append to a location in the KB if and only if there it no other
        vulnerability in the same location for the same URL and parameter.

        Does this in a thread-safe manner.

        :param location_a: The A location where to store data

        :param location_b: The B location where to store data

        :param info_inst: An Info instance (or subclasses like Vuln and InfoSet)

        :param filter_by: One of 'VAR' of 'URL'. Only append to the kb in
                          (location_a, location_b) if there is NO OTHER info
                          in that location with the same:
                              - 'VAR': URL,Variable,DataContainer.keys()
                              - 'URL': URL

        :return: True if the vuln was added. False if there was already a
                 vulnerability in the KB location with the same URL and
                 parameter.
        """
        if not isinstance(info_inst, Info):
            raise TypeError("append_uniq requires an info object as parameter.")

        filter_function = self.FILTERS.get(filter_by, None)

        if filter_function is None:
            raise ValueError("append_uniq only knows about URL or VAR filters.")

        with self._kb_lock:

            if filter_function(location_a, location_b, info_inst):
                self.append(location_a, location_b, info_inst)
                return True

            return False

    def filter_url(self, location_a, location_b, info_inst):
        """
        :return: True if there is no other info in (location_a, location_b)
                 with the same URL as the info_inst.
        """
        for saved_vuln in self.get_iter(location_a, location_b):
            if saved_vuln.get_url() == info_inst.get_url():
                return False

        return True

    def filter_var(self, location_a, location_b, info_inst):
        """
        :return: True if there is no other info in (location_a, location_b)
                 with the same URL, variable as the info_inst.

                 Before I checked the data container parameter names
                 the problem with that approach was that in some rare
                 cases the scanner reported vulnerabilities in:

                    http://target.com/?id={here}&tracking1=23
                    http://target.com/?id={here}&tracking1=23&tracking2=42

                 Where tracking1 and tracking2 were parameters added
                 for tracking the user navigation through the site.

                 Then I realized that this is the same vulnerability
                 since the same piece of code is the one generating
                 them. Thus, no need to report them twice.

        """
        for saved_vuln in self.get_iter(location_a, location_b):

            if saved_vuln.get_token_name() != info_inst.get_token_name():
                continue

            if saved_vuln.get_url() != info_inst.get_url():
                continue

            msg = (
                '[filter_var] Preventing "%s" from being written to the'
                ' KB because "%s" has the same token (%s) and URL (%s).'
            )
            args = (
                info_inst.get_desc(),
                saved_vuln.get_desc(),
                info_inst.get_token_name(),
                info_inst.get_url(),
            )
            LOGGER.debug(msg, *args)

            return False

        return True

    def _has_reached_max_info_instances(
        self, location_a, location_b, info_inst, group_klass
    ):
        """
        Checks if the tuple containing
            - location_a,
            - location_b,
            - info.get(self.ITAG)

        Is in the max info instances reached cache.

        Works together with _record_reached_max_info_instances()

        :param location_a: The "a" address
        :param location_b: The "b" address
        :param info_inst: The Info instance we want to store
        :param group_klass: If required, will be used to create a new InfoSet
        :return: The cached InfoSet or None if it has not been recorded.
        """
        key = self._get_max_info_instances_key(
            location_a, location_b, info_inst, group_klass
        )
        return self._reached_max_info_instances_cache.get(key)

    def _get_max_info_instances_key(
        self, location_a, location_b, info_inst, group_klass
    ):
        return (location_a, location_b, repr(info_inst.get(group_klass.ITAG)))

    def _record_reached_max_info_instances(
        self, location_a, location_b, info_inst, group_klass, info_set
    ):
        """
        Stores the tuple containing
            - location_a,
            - location_b,
            - info.get(self.ITAG)

        To the max info instances reached cache.

        Works together with _has_reached_max_info_instances()

        :param location_a: The "a" address
        :param location_b: The "b" address
        :param info_inst: The Info instance we want to store
        :param group_klass: If required, will be used to create a new InfoSet
        :param info_set: The matching InfoSet to cache
        :return: None
        """
        key = self._get_max_info_instances_key(
            location_a, location_b, info_inst, group_klass
        )
        self._reached_max_info_instances_cache[key] = copy.deepcopy(info_set)

    def append_uniq_group(self, location_a, location_b, info_inst, group_klass=InfoSet):
        """
        This function will append a Info instance to an existing InfoSet which
        is stored in (location_a, location_b) and matches the filter_func.

        If filter_func doesn't match any existing InfoSet instances, then a new
        one is created using `group_klass` and `info_inst` is appended to it.

        :see: https://github.com/andresriancho/w3af/issues/3955

        :param location_a: The "a" address
        :param location_b: The "b" address
        :param info_inst: The Info instance we want to store
        :param group_klass: If required, will be used to create a new InfoSet
        :return: (The updated/created InfoSet, as stored in the kb,
                  True if a new InfoSet was created)
        """
        if not isinstance(info_inst, Info):
            raise TypeError(
                "append_uniq_group requires an Info instance" " as parameter."
            )

        if not issubclass(group_klass, InfoSet):
            raise TypeError(
                "append_uniq_group requires an InfoSet subclass" " as parameter."
            )

        location_a = self._get_real_name(location_a)

        with self._kb_lock:

            # This performs a quick check against a LRU cache to prevent
            # queries to the DB
            cached_info_set = self._has_reached_max_info_instances(
                location_a, location_b, info_inst, group_klass
            )
            if cached_info_set is not None:
                return copy.deepcopy(cached_info_set), False

            for info_set in self.get_iter(location_a, location_b):
                if not isinstance(info_set, InfoSet):
                    continue

                if info_set.match(info_inst):
                    # InfoSet will only store a MAX_INFO_INSTANCES inside, after
                    # that any calls to add() will not modify InfoSet.infos
                    if info_set.has_reached_max_info_instances():

                        # Record that this location and infoset have reached the max
                        # instances. This works together with _has_reached_max_info_instances()
                        # to reduce SQLite queries
                        self._record_reached_max_info_instances(
                            location_a, location_b, info_inst, group_klass, info_set
                        )

                        # The info set instance was not modified, so we just return
                        return info_set, False

                    # Since MAX_INFO_INSTANCES has not been reached, we need to
                    # copy the info set, add the info instance, and update the DB
                    old_info_set = copy.deepcopy(info_set)

                    # Add the new information to the InfoSet instance, if we reach
                    # this point, and because we checked against has_reached_max_info_instances,
                    # we are sure that `added` will be True and the info instance
                    # will be added to the InfoSet
                    added = info_set.add(info_inst)

                    # Only change the ID of the InfoSet instance if a new Info
                    # has been added
                    if added:
                        info_set.generate_new_id()

                    # Save to the DB
                    self.update(old_info_set, info_set)

                    return info_set, False
            # No pre-existing InfoSet instance matched, let's create one
            # for the info_inst
            info_set = group_klass([info_inst])
            self.append(location_a, location_b, info_set)
            return info_set, True

    def get_all_findings(self, exclude_ids=()):
        """
        :return: A list of all findings, including Info, Vuln and InfoSet.
        :param exclude_ids: The vulnerability IDs to exclude from the result
        """
        return self.get_all_entries_of_class(
            (Info, InfoSet, Vuln), exclude_ids=exclude_ids
        )

    def get_all_findings_iter(self, exclude_ids=()):
        """
        An iterated version of get_all_findings. All new code should use
        get_all_findings_iter instead of get_all_findings().

        :yield: All findings stored in the KB.
        :param exclude_ids: The vulnerability IDs to exclude from the result
        """
        klass = (Info, InfoSet, Vuln)

        yield from self.get_all_entries_of_class_iter(klass, exclude_ids)

    def get_all_shells(self, w3af_core=None):
        """
        :param w3af_core: The w3af_core used in the current scan
        @see: Shell.__reduce__ to understand why we need the w3af_core
        :return: A list of all vulns reported by all plugins.
        """
        all_shells = []

        for shell in self.get_all_entries_of_class(Shell):
            if w3af_core is not None:
                shell.set_url_opener(w3af_core.uri_opener)
                shell.set_worker_pool(w3af_core.worker_pool)

            all_shells.append(shell)

        return all_shells

    def _get_real_name(self, data):
        """
        Some operations allow location_a to be both a plugin instance or a string.

        Those operations will call this method to translate the plugin instance
        into a string.
        """
        if isinstance(data, str):
            return data
        else:
            return data.get_name()
