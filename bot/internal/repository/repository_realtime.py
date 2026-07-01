"""Compatibility shim for the canonical realtime repository implementation."""

from src.infrastructure.persistence.repository_realtime import (
    AlertRepository,
    MarketDataRepository,
    PositionRepository,
    PositionSnapshotsRepository,
    StatsRepository,
    UnitOfWorkRealtime,
)

__all__ = [
    "AlertRepository",
    "MarketDataRepository",
    "PositionRepository",
    "PositionSnapshotsRepository",
    "StatsRepository",
    "UnitOfWorkRealtime",
]
