"""Advisor-scoped RNG; retain standard random semantics for other callers."""
from contextvars import ContextVar
from functools import wraps
import random as _standard

_request_rng = ContextVar("advisor_rng", default=None)

def _source():
    value = _request_rng.get()
    return _standard if value is None else value

def random():
    return _source().random()

def choice(values):
    return _source().choice(values)

def seed(value=None):
    return _source().seed(value)

def seeded_request(value):
    """Start the same sequence on each call without sharing it across requests."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            token = _request_rng.set(_standard.Random(value))
            try:
                return function(*args, **kwargs)
            finally:
                _request_rng.reset(token)
        return wrapped
    return decorate
