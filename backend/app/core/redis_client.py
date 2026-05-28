from functools import lru_cache

from redis import Redis


@lru_cache
def get_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url)

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
