"""Cache and lock service contracts for the staged Valkey migration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class CacheLockService(ABC):
    """Temporary coordination only: cache, TTL locks, dedupe, and leases."""

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """Read a short-lived value from the cache layer."""

    @abstractmethod
    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        """Write a short-lived value with an explicit TTL."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a temporary key."""

    @abstractmethod
    def acquire_lock(self, key: str, token: str, *, ttl_seconds: int) -> bool:
        """Acquire a TTL-bound lock for short-lived coordination."""

    @abstractmethod
    def release_lock(self, key: str, token: str) -> bool:
        """Release a lock only when the ownership token matches."""


class ValkeyCacheLockService(CacheLockService):
    """Phase 1 placeholder for the future Valkey-backed implementation."""

    def __init__(self, *, enabled: bool = False, url: str = ""):
        self.enabled = enabled
        self.url = url

    def get(self, key: str) -> Optional[str]:
        del key
        raise RuntimeError(
            "Valkey cache/lock service is not wired in Phase 1. "
            "Existing direct Redis-compatible paths remain authoritative for now."
        )

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        del key, value, ttl_seconds
        raise RuntimeError(
            "Valkey cache/lock service is not wired in Phase 1. "
            "Use existing direct Redis-compatible paths until Phase 5."
        )

    def delete(self, key: str) -> None:
        del key
        raise RuntimeError(
            "Valkey cache/lock service is not wired in Phase 1. "
            "Use existing direct Redis-compatible paths until Phase 5."
        )

    def acquire_lock(self, key: str, token: str, *, ttl_seconds: int) -> bool:
        del key, token, ttl_seconds
        raise RuntimeError(
            "Valkey cache/lock service is not wired in Phase 1. "
            "Use existing direct Redis-compatible paths until Phase 5."
        )

    def release_lock(self, key: str, token: str) -> bool:
        del key, token
        raise RuntimeError(
            "Valkey cache/lock service is not wired in Phase 1. "
            "Use existing direct Redis-compatible paths until Phase 5."
        )
