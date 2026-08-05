from collections import OrderedDict


class Cache:

    def __init__(self, max_size=100):

        self.max_size = max_size

        self.cache = OrderedDict()

    def get(self, key):

        if key not in self.cache:
            return None

        self.cache.move_to_end(key)

        return self.cache[key]

    def set(self, key, value):

        self.cache[key] = value

        self.cache.move_to_end(key)

        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def clear(self):

        self.cache.clear()

    def has(self, key):

        return key in self.cache

    def size(self):

        return len(self.cache)


lyrics_cache = Cache(100)