"""Prepare the directories used by a w3af process."""

import os
import sys

from w3af.core.controllers.misc.home_dir import create_home_dir, verify_dir_has_perm
from w3af.core.filesystem import TEMP_DIR, create_temp_dir
from w3af.core.paths import get_home_dir


def prepare_home_directory():
    """Create and validate the user's w3af home directory."""
    home_dir = get_home_dir()

    if not create_home_dir():
        print(f'Failed to create the w3af home directory "{home_dir}".')
        sys.exit(-3)

    if not verify_dir_has_perm(home_dir, perm=os.W_OK | os.R_OK, levels=1):
        print(
            f'Either the w3af home directory "{home_dir}" or its contents are not'
            " writable or readable. Please set the correct permissions"
            " and ownership. This usually happens when running w3af as"
            ' root using "sudo".'
        )
        sys.exit(-3)


def prepare_tmp_directory():
    """Create the temporary directory used by a w3af scan."""
    try:
        create_temp_dir()
    except OSError:
        msg = (
            f'The w3af tmp directory "{TEMP_DIR}" is not writable. Please set '
            "the correct permissions and ownership."
        )
        print(msg)
        sys.exit(-3)
