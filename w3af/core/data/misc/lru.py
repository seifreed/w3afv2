from collections import OrderedDict
from threading import RLock


class LRUDict:
    def __init__(self, capacity=1024):
        if capacity < 1:
            raise ValueError("capacity must be greater than zero")
        self.capacity = capacity
        self._items = OrderedDict()

    def __getitem__(self, key):
        value = self._items.pop(key)
        self._items[key] = value
        return value

    def __setitem__(self, key, value):
        self._items.pop(key, None)
        self._items[key] = value
        if len(self._items) > self.capacity:
            self._items.popitem(last=False)

    def __delitem__(self, key):
        del self._items[key]

    def __contains__(self, key):
        if key not in self._items:
            return False
        self[key]
        return True

    def __iter__(self):
        return iter(tuple(self._items))

    def __len__(self):
        return len(self._items)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def clear(self):
        self._items.clear()

    def keys(self):
        return tuple(self._items)

    def values(self):
        return tuple(self._items.values())

    def items(self):
        return tuple(self._items.items())


class SynchronizedLRUDict:
    def __init__(self, capacity=1024):
        self._cache = LRUDict(capacity)
        self._lock = RLock()

    def __getitem__(self, key):
        with self._lock:
            return self._cache[key]

    def __setitem__(self, key, value):
        with self._lock:
            self._cache[key] = value

    def __delitem__(self, key):
        with self._lock:
            del self._cache[key]

    def __contains__(self, key):
        with self._lock:
            return key in self._cache

    def __iter__(self):
        with self._lock:
            return iter(tuple(self._cache))

    def __len__(self):
        with self._lock:
            return len(self._cache)

    def get(self, key, default=None):
        with self._lock:
            return self._cache.get(key, default)

    def clear(self):
        with self._lock:
            self._cache.clear()

    def keys(self):
        with self._lock:
            return self._cache.keys()

    def values(self):
        with self._lock:
            return self._cache.values()

    def items(self):
        with self._lock:
            return self._cache.items()
