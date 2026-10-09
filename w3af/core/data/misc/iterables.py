"""Order-preserving iterable helpers."""

import hashlib
import itertools
import operator
from collections.abc import Callable, Hashable, Iterable, Iterator
from typing import TypeVar

from w3af.core.data.misc.encoding import smart_str_ignore

T = TypeVar("T", bound=Hashable)


def unique_everseen(
    iterable: Iterable[T], key: Callable[[T], Hashable] | None = None
) -> Iterator[T]:
    """Yield unique elements in first-seen order."""
    seen: set[Hashable] = set()
    seen_add = seen.add
    if key is None:
        for element in itertools.filterfalse(seen.__contains__, iterable):
            seen_add(element)
            yield element
    else:
        for element in iterable:
            key_value = key(element)
            if key_value not in seen:
                seen_add(key_value)
                yield element


def unique_justseen(
    iterable: Iterable[T], key: Callable[[T], Hashable] | None = None
) -> Iterator[T]:
    """Yield one element from each consecutive group of equal values."""
    groupby = itertools.groupby
    itemgetter = operator.itemgetter
    return map(next, map(itemgetter(1), groupby(iterable, key)))


def unique_everseen_hash(iterable: Iterable[str]) -> Iterator[str]:
    """Yield unique strings in first-seen order, retaining only their hashes."""
    seen = set()

    for element in iterable:
        element_hash = hashlib.sha256(smart_str_ignore(element)).digest()
        if element_hash not in seen:
            seen.add(element_hash)
            yield element
