from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class LockProvider(ABC):
    """Abstract contract for distributed coordination: a lock plus a
    small shared key-value space for publishing results.

    Together these enable *single-flight imports with result sharing*:
    when N concurrent requests ask for the same import, exactly one
    acquires the lock and does the work; the rest wait and read the
    winner's published result instead of duplicating SWAPI traffic and
    database writes. Works across ALL processes/workers — something an
    in-process primitive (e.g. `asyncio.Semaphore`) cannot do.

    The concrete implementation (Redis-backed) lives in the
    infrastructure layer.
    """

    @abstractmethod
    async def acquire(self, key: str, token: str, ttl_seconds: int) -> bool:
        """Attempts to acquire the lock identified by `key`.

        Args:
            key: Lock name, e.g. "import:lock:films".
            token: Unique value identifying this holder (e.g. a UUID), so
                only the rightful owner can release it later.
            ttl_seconds: Auto-expiry. Prevents a permanent deadlock if the
                process holding the lock crashes before releasing.

        Returns:
            True if the lock was acquired, False if it is already held.
        """
        ...

    @abstractmethod
    async def release(self, key: str, token: str) -> bool:
        """Releases the lock, but only if `token` still matches the
        current holder — so a process whose lock already expired can't
        accidentally release a lock re-acquired by someone else.

        Args:
            key: Lock name previously passed to `acquire`.
            token: The same unique token used to acquire.

        Returns:
            True if the lock was released, False otherwise.
        """
        ...

    @abstractmethod
    async def set_value(self, key: str, value: str, ttl_seconds: int) -> None:
        """Publishes a value (e.g. a serialized import result) so other
        waiting processes can read it.

        Args:
            key: Value key, e.g. "import:result:films".
            value: Serialized payload.
            ttl_seconds: How long the value stays readable before expiring.
        """
        ...

    @abstractmethod
    async def get_value(self, key: str) -> Optional[str]:
        """Reads a previously published value.

        Args:
            key: Value key previously passed to `set_value`.

        Returns:
            The value, or None if absent/expired.
        """
        ...