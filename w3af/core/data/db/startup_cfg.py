"""
startup_cfg.py

Copyright 2011 Andres Riancho

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

import configparser
import os
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from w3af.core.data.misc.local_date import local_today
from w3af.core.paths import get_home_dir


class StartUpConfig:
    """
    Wrapper class for ConfigParser.ConfigParser.
    Holds the configuration for the VersionMgr update/commit process
    """

    ISO_DATE_FMT = "%Y-%m-%d"
    # Frequency constants
    FREQ_DAILY = "D"  # [D]aily
    FREQ_WEEKLY = "W"  # [W]eekly
    FREQ_MONTHLY = "M"  # [M]onthly
    # DEFAULT VALUES
    DEFAULTS: ClassVar[dict[str, str]] = {
        "auto-update": "true",
        "frequency": "D",
        "last-update": "None",
        "last-commit": "",
        "accepted-disclaimer": "false",
        "skip-dependencies-check": "false",
    }

    def __init__(self, cfg_file=None):
        """
        :param cfg_file: The configuration file, by default startup.conf in
                         the w3af home directory at the time of the call
        """
        if cfg_file is None:
            cfg_file = os.path.join(get_home_dir(), "startup.conf")

        self._start_cfg_file = cfg_file
        self._start_section = "STARTUP_CONFIG"

        self._config = configparser.ConfigParser()
        configs = self._load_cfg()

        (
            self._autoupd,
            self._freq,
            self._lastupd,
            self._last_commit_id,
            self._accepted_disclaimer,
            self._skip_dependencies_check,
        ) = configs

    ### METHODS #

    def get_last_upd(self):
        """
        Getter method.
        """
        return self._lastupd

    def set_last_upd(self, datevalue):
        """
        :param datevalue: datetime.date value
        """
        self._lastupd = datevalue
        self._config.set(self._start_section, "last-update", datevalue.isoformat())

    def get_skip_dependencies_check(self):
        return self._skip_dependencies_check

    def set_skip_dependencies_check(self, skip):
        self._skip_dependencies_check = skip
        value = "true" if skip else "false"
        self._config.set(self._start_section, "skip-dependencies-check", value)

    def get_accepted_disclaimer(self):
        return self._accepted_disclaimer

    def set_accepted_disclaimer(self, accepted_decision):
        """
        :param datevalue: datetime.date value
        """
        self._accepted_disclaimer = accepted_decision
        value = "true" if accepted_decision else "false"
        self._config.set(self._start_section, "accepted-disclaimer", value)

    def get_last_commit_id(self):
        return self._last_commit_id

    def set_last_commit_id(self, commit_id):
        if not isinstance(commit_id, str):
            raise TypeError(f"Expected string got {type(commit_id)} instead.")

        self._last_commit_id = commit_id
        self._config.set(self._start_section, "last-commit", self._last_commit_id)

    def get_freq(self):
        return self._freq

    def get_auto_upd(self):
        return self._autoupd

    def _get_bool_val(self, key, default=False):
        boolvals = {"false": 0, "off": 0, "no": 0, "true": 1, "on": 1, "yes": 1}

        # pylint: disable=E1103
        # E1103: Instance of '_Chainmap' has no 'lower' member
        #        (but some types could not be inferred)",
        val = self._config.get(self._start_section, key, raw=True)
        val = bool(boolvals.get(val.lower(), default))
        return val

    def _load_cfg(self):
        """
        Loads configuration from config file.
        """
        config = self._config
        startsection = self._start_section
        if not config.has_section(startsection):
            config.add_section(startsection)
            defaults = StartUpConfig.DEFAULTS
            for key in self.DEFAULTS:
                config.set(startsection, key, defaults[key])

        # Read from file
        config.read(self._start_cfg_file, encoding="utf-8")

        auto_upd = self._get_bool_val("auto-update")
        accepted_disclaimer = self._get_bool_val("accepted-disclaimer")
        skip_dependencies_check = self._get_bool_val("skip-dependencies-check")

        freq = config.get(startsection, "frequency", raw=True).upper()
        if freq not in (
            StartUpConfig.FREQ_DAILY,
            StartUpConfig.FREQ_WEEKLY,
            StartUpConfig.FREQ_MONTHLY,
        ):
            freq = StartUpConfig.FREQ_DAILY

        lastupdstr = config.get(startsection, "last-update", raw=True).upper()
        # Try to parse it
        try:
            lastupd = (
                datetime.strptime(lastupdstr, self.ISO_DATE_FMT)
                .replace(tzinfo=UTC)
                .date()
            )
        except ValueError:
            # Provide default value that enforces the update to happen
            lastupd = local_today() - timedelta(days=31)
        lastrev = config.get(startsection, "last-commit")
        return (
            auto_upd,
            freq,
            lastupd,
            lastrev,
            accepted_disclaimer,
            skip_dependencies_check,
        )

    def save(self):
        """
        Saves current values to cfg file
        """
        with open(self._start_cfg_file, "w", encoding="utf-8") as configfile:
            self._config.write(configfile)

    ### PROPERTIES #

    freq = property(get_freq)
    auto_upd = property(get_auto_upd)
    last_commit_id = property(get_last_commit_id, set_last_commit_id)
    accepted_disclaimer = property(get_accepted_disclaimer, set_accepted_disclaimer)
    last_upd = property(get_last_upd, set_last_upd)
    skip_dependencies_check = property(
        get_skip_dependencies_check, set_skip_dependencies_check
    )
