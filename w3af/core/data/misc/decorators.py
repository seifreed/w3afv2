"""Shared decorators for data and application layers."""

import functools

from w3af.core.data.misc.lru import SynchronizedLRUDict


class Memoized:
    """Cache decorated calls in a bounded, thread-safe LRU cache."""

    def __init__(self, func, lru_size=10):
        self.func = func
        self.cache = SynchronizedLRUDict(lru_size)

    def __call__(self, *args, **kwargs):
        key = (args, tuple(kwargs.items()))
        try:
            return self.cache[key]
        except KeyError:
            result = self.func(*args, **kwargs)
            self.cache[key] = result
            return result

    def __repr__(self):
        return self.func.__doc__

    def __get__(self, instance, instance_type):
        return functools.partial(self, instance)
