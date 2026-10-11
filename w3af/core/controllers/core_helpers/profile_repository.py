"""Persist and enumerate profile files."""

import os

from w3af.core.controllers.misc.get_file_list import get_file_list
from w3af.core.data.profile.profile import profile
from w3af.core.exceptions import BaseFrameworkException
from w3af.core.paths import get_home_dir


class ProfileRepository:
    """Own filesystem operations for framework profiles."""

    def create(self, profile_name, profile_desc):
        profile_instance = profile()
        profile_instance.set_desc(profile_desc)
        profile_instance.set_name(profile_name)
        profile_instance.save(profile_name)
        return profile_instance

    def load(self, profile_name, workdir=None):
        return profile(profile_name, workdir)

    def load_for_path(self, profile_name, profile_path):
        return self.load(profile_name, workdir=os.path.dirname(profile_path))

    def list_profiles(self, directory=None):
        directory = directory or get_home_dir()
        profile_home = os.path.join(directory, "profiles")
        profile_names = get_file_list(profile_home, extension=profile.EXTENSION)

        valid_profiles = []
        invalid_profiles = []
        for profile_name in profile_names:
            profile_filename = os.path.join(
                profile_home, profile_name + profile.EXTENSION
            )
            try:
                profile_instance = profile(profile_filename)
            except BaseFrameworkException:
                invalid_profiles.append(profile_filename)
            else:
                valid_profiles.append(profile_instance)

        return valid_profiles, invalid_profiles

    def remove(self, profile_name):
        profile_instance = profile(profile_name)
        profile_instance.remove()
        return True
