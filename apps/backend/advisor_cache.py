"""Bounded exact-result cache with one in-flight calculation per ordered key.

A sealed deployment fixes all game data and abstract-simulator code. Values are
JSON copies, never mutable shared results. Errors and exceptions are not cached.
"""
from collections import OrderedDict
from concurrent.futures import Future
from functools import wraps
import json
from threading import Lock

class ExactCache:
    def __init__(self, revision, max_entries=256, max_bytes=8_000_000):
        self.revision = revision
        self.max_entries, self.max_bytes = max_entries, max_bytes
        self.values, self.pending = OrderedDict(), {}
        self.bytes = 0
        self.lock = Lock()

    def wrap(self, kind, function):
        @wraps(function)
        def cached(left, right, age='imperial'):
            key = (self.revision, kind, left, right, age)
            with self.lock:
                if key in self.values:
                    self.values.move_to_end(key)
                    return json.loads(self.values[key])
                future = self.pending.get(key)
                owner = future is None
                if owner:
                    future = self.pending[key] = Future()
            if not owner:
                return json.loads(future.result())
            try:
                value = function(left, right, age)
                encoded = json.dumps(value, ensure_ascii=False).encode()
                if 'error' not in value:
                    with self.lock:
                        if len(encoded) <= self.max_bytes:
                            self.values[key] = encoded
                            self.bytes += len(encoded)
                            while len(self.values) > self.max_entries or self.bytes > self.max_bytes:
                                self.bytes -= len(self.values.popitem(last=False)[1])
                future.set_result(encoded)
                return json.loads(encoded)
            except BaseException as error:
                future.set_exception(error)
                raise
            finally:
                with self.lock: self.pending.pop(key, None)
        return cached
