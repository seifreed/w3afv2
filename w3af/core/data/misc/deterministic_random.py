"""
deterministic_random.py

Copyright 2024 Andres Riancho

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

import random

# Several scanner components need a *reproducible* stream of pseudo-random
# values: generating the exact same fake 404 probe URLs, bloom-filter hash
# seeds or evasion payloads across runs is what makes their results
# comparable and their caches valid. That requirement rules out a
# cryptographically secure generator (which, by design, cannot be seeded to
# replay a sequence) and makes the seedable Mersenne Twister the correct
# tool here.
#
# This generator is therefore used ONLY for non-security randomness. Anything
# that must be unpredictable to an attacker (keys, nonces, tokens) uses the
# ``secrets`` module instead.
_MersenneTwister = random.Random


def get_deterministic_random(seed=None):
    """
    :param seed: Optional seed that makes the generated sequence reproducible.
    :return: A non-cryptographic, seedable pseudo-random generator.
    """
    generator = _MersenneTwister()
    if seed is not None:
        generator.seed(seed)
    return generator
