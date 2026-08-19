"""Small thread-safe TTL cache used to memoize slow external API calls."""
import threading
import time
from functools import wraps

# Registry of every cached function so callers (e.g. startup warming)
# can inspect or clear them if needed.
_registries = []


def ttl_cache(seconds: float):
    """
    Decorator that caches a function's return value per-arguments
    for `seconds`. Safe to call from multiple threads.

    Only use on functions whose arguments are hashable.
    Exceptions are never cached.
    """
    def decorator(func):
        cache: dict = {}
        lock = threading.Lock()

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            with lock:
                entry = cache.get(key)
                if entry is not None and now - entry[1] < seconds:
                    return entry[0]

            value = func(*args, **kwargs)

            with lock:
                cache[key] = (value, time.monotonic())
            return value

        def cache_clear():
            with lock:
                cache.clear()

        wrapper.cache_clear = cache_clear
        _registries.append(wrapper)
        return wrapper

    return decorator


def clear_all_caches():
    """Clear every TTL cache (useful for tests)."""
    for func in _registries:
        func.cache_clear()
