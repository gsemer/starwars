from __future__ import annotations

import logging
from typing import Optional

from redis.asyncio import Redis

from app.domain.interfaces.lock_provider import LockProvider

# Lua script makes check-and-delete atomic: the key is deleted only if it
# still holds OUR token. Without this, a holder whose TTL already expired
# could release a lock that a different process has since acquired.
_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


class RedisLockProvider(LockProvider):
    """Redis-backed distributed lock.

    Acquisition uses `SET key token NX PX ttl` — a single atomic command
    that sets the key only if it doesn't exist AND attaches an expiry, so
    there is no race window between "check" and "set", and a crashed
    holder can never deadlock the lock forever (the TTL clears it).
    """

    def __init__(self, redis_client: Redis, logger: logging.Logger) -> None:
        """
        Args:
            redis_client: Shared async Redis client (owned by the Container).
            logger: Shared application logger.
        """
        self._redis = redis_client
        self._logger = logger

    async def acquire(self, key: str, token: str, ttl_seconds: int) -> bool:
        """See `LockProvider.acquire`."""
        acquired = await self._redis.set(key, token, nx=True, px=ttl_seconds * 1000)
        if not acquired:
            self._logger.info("lock_busy key=%s", key)
        return bool(acquired)

    async def release(self, key: str, token: str) -> bool:
        """See `LockProvider.release`."""
        released = bool(await self._redis.eval(_RELEASE_SCRIPT, 1, key, token))
        if not released:
            self._logger.warning("lock_release_failed key=%s (expired or not owner)", key)
        return released

    async def set_value(self, key: str, value: str, ttl_seconds: int) -> None:
        """See `LockProvider.set_value`."""
        await self._redis.set(key, value, ex=ttl_seconds)

    async def get_value(self, key: str) -> Optional[str]:
        """See `LockProvider.get_value`."""
        value = await self._redis.get(key)
        return value.decode() if isinstance(value, bytes) else value
