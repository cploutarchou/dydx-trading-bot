"""
Pair storage models and persistence layer for cointegration analysis results.

This module provides data structures and utilities for storing and retrieving
cointegration analysis results, including enhanced metrics and confidence scoring.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.orm import Session


def _resolve_pair_storage_path() -> str:
    """Resolve pair storage path from the environment for multi-instance mode."""
    configured_path = os.getenv("BOT_PAIRS_FILE")
    if not configured_path:
        return "pair_history/cointegration_results.json"

    instance_id = os.getenv("BOT_INSTANCE_ID", "default")
    return configured_path.replace("{instance_id}", instance_id)


@dataclass
class CointegrationResult:
    """
    Enhanced cointegration analysis result with confidence scoring.

    Stores all relevant metrics from pair analysis including statistical
    measures and trading signals.
    """

    base_market: str
    quote_market: str
    hedge_ratio: float
    half_life: float
    zero_crossings: int
    p_value: float
    z_score_mean: float
    z_score_std: float
    analysis_timestamp: str
    confidence_score: float
    creation_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # OLS intercept of series_1 ~ const + hedge_ratio * series_2. Defaults to
    # 0.0 so pairs persisted before this field existed deserialize unchanged.
    # Live z-scores must subtract it to match the fitted spread.
    intercept: float = 0.0

    @property
    def is_high_confidence(self) -> bool:
        """Returns True if the confidence score is above the threshold (0.7)."""
        return self.confidence_score >= 0.7

    @property
    def pair_name(self) -> str:
        """Returns formatted pair name."""
        return f"{self.base_market}_{self.quote_market}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CointegrationResult":
        """Create instance from dictionary."""
        return cls(**data)


def calculate_confidence_score(
    p_value: float,
    half_life: float,
    zero_crossings: int,
    max_half_life: float = 14.0,
    min_zero_crossings: int = 5,
) -> float:
    """
    Calculate a confidence score for a cointegrated pair.

    Score combines multiple factors:
    - P-value contribution: Lower is better (0.05 ideal)
    - Half-life contribution: Shorter half-life is more mean-reverting (ideal < 14)
    - Zero-crossings contribution: More crossings = better mean reversion

    Args:
        p_value: Cointegration test p-value (lower is better, ideal 0.05)
        half_life: Mean reversion half-life in periods
        zero_crossings: Number of zero crossings in spread Z-score
        max_half_life: Maximum acceptable half-life for scaling
        min_zero_crossings: Minimum zero crossings for full score

    Returns:
        float: Confidence score between 0.0 and 1.0
    """
    try:
        # P-value component (0 to 0.4): lower p-value = higher score
        # Normalize to 0.05 as ideal
        p_value_score = max(0, min(0.4, 0.4 * (0.05 / max(p_value, 0.001))))

        # Half-life component (0 to 0.35): shorter half-life = higher score
        # Normalize to max_half_life
        half_life_ratio = min(1.0, max_half_life / max(half_life, 0.1))
        half_life_score = 0.35 * half_life_ratio

        # Zero-crossings component (0 to 0.25): more crossings = higher score
        # Normalize to min_zero_crossings
        if zero_crossings >= min_zero_crossings:
            zc_score = 0.25
        else:
            zc_score = 0.25 * (zero_crossings / max(min_zero_crossings, 1))

        # Combine components
        total_score = p_value_score + half_life_score + zc_score

        # Ensure score is within bounds
        return min(1.0, max(0.0, total_score))

    except Exception as e:
        logger.warning(f"Error calculating confidence score: {e}")
        return 0.5  # Default to neutral score on error


def _get_instance_id() -> str:
    return os.getenv("BOT_INSTANCE_ID", "default")


class PairStorage:
    """
    Manages persistence of cointegration analysis results.

    Database is the primary store; the JSON file is kept as a fallback for
    environments without a reachable database.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize pair storage.

        Args:
            storage_path: Path to JSON storage file. If not provided, resolves from
                BOT_PAIRS_FILE (or defaults to pair_history/cointegration_results.json).
        """
        resolved_path = storage_path or _resolve_pair_storage_path()
        self.storage_path = Path(resolved_path)
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Ensure a storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _db_save(self, storage_data: dict[str, Any]) -> bool:
        """Upsert cointegration results into the database. Returns True on success.
        :rtype: bool
        """
        try:
            from sqlalchemy import text

            from src.infrastructure.database import db

            instance_id = _get_instance_id()
            pairs_count = storage_data.get("total_pairs", 0)
            high_confidence_count = storage_data.get("high_confidence_pairs", 0)
            analyzed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session = db.get_session()
            try:
                existing = session.execute(
                    text("SELECT id FROM cointegrated_pairs WHERE instance_id = :iid"),
                    {"iid": instance_id},
                ).fetchone()
                if existing:
                    session.execute(
                        text(
                            "UPDATE cointegrated_pairs "
                            "SET pairs_json = :pj, pairs_count = :pc, "
                            "high_confidence_count = :hc, analyzed_at = :aa "
                            "WHERE instance_id = :iid"
                        ),
                        {
                            "pj": json.dumps(storage_data),
                            "pc": pairs_count,
                            "hc": high_confidence_count,
                            "aa": analyzed_at,
                            "iid": instance_id,
                        },
                    )
                else:
                    session.execute(
                        text(
                            "INSERT INTO cointegrated_pairs "
                            "(instance_id, pairs_json, pairs_count, high_confidence_count, analyzed_at) "
                            "VALUES (:iid, :pj, :pc, :hc, :aa)"
                        ),
                        {
                            "iid": instance_id,
                            "pj": json.dumps(storage_data),
                            "pc": pairs_count,
                            "hc": high_confidence_count,
                            "aa": analyzed_at,
                        },
                    )
                session.commit()
                return True
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        except Exception as exc:
            logger.debug(
                f"DB save cointegrated pairs failed ({exc}); falling back to file"
            )
            return False

    def _db_load(self) -> Optional[dict[str, Any]]:
        """Load cointegration results from the database. Returns None if unavailable."""
        try:
            from sqlalchemy import text

            from src.infrastructure.database import db

            instance_id = _get_instance_id()
            session = db.get_session()
            try:
                result = session.execute(
                    text(
                        "SELECT pairs_json FROM cointegrated_pairs WHERE instance_id = :iid"
                    ),
                    {"iid": instance_id},
                ).fetchone()
                if result is None:
                    return None
                data = result[0]
                if isinstance(data, str):
                    data = json.loads(data)
                return data if isinstance(data, dict) else None
            finally:
                session.close()
        except Exception as exc:
            logger.debug(
                f"DB load cointegrated pairs failed ({exc}); using file fallback"
            )
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_pairs(self, pairs: List[CointegrationResult]) -> dict[str, Any]:
        """
        Save cointegration results to storage (DB primary, file fallback).

        Args:
            pairs: List of CointegrationResult objects

        Returns:
            dict: Result metadata including number of pairs saved
        """
        pairs_data = [pair.to_dict() for pair in pairs]
        high_confidence = len([p for p in pairs if p.is_high_confidence])
        storage_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_pairs": len(pairs),
            "high_confidence_pairs": high_confidence,
            "pairs": pairs_data,
        }

        if self._db_save(storage_data):
            logger.info(
                f"Saved {len(pairs)} cointegration results to database (instance={_get_instance_id()})"
            )
        else:
            # File fallback
            try:
                with open(self.storage_path, "w") as f:
                    json.dump(storage_data, f, indent=2)
                logger.info(
                    f"Saved {len(pairs)} cointegration results to {self.storage_path}"
                )
            except Exception as e:
                logger.error(f"Error saving pairs to {self.storage_path}: {e}")
                return {"success": False, "error": str(e)}

        return {
            "success": True,
            "pairs_saved": len(pairs),
            "high_confidence": high_confidence,
        }

    def load_pairs(self) -> List[CointegrationResult]:
        """
        Load cointegration results from storage (DB primary, file fallback).

        Returns:
            List of CointegrationResult objects, or empty list if not found
        """
        # Try DB first
        storage_data = self._db_load()

        # Fall back to file
        if storage_data is None:
            try:
                if not self.storage_path.exists():
                    logger.debug(f"No pairs file found at {self.storage_path}")
                    return []
                with open(self.storage_path, "r") as f:
                    storage_data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading pairs from {self.storage_path}: {e}")
                return []

        pairs = [
            CointegrationResult.from_dict(pair_data)
            for pair_data in storage_data.get("pairs", [])
        ]
        logger.info(f"Loaded {len(pairs)} cointegration results")
        return pairs

    def get_high_confidence_pairs(self) -> List[CointegrationResult]:
        """Load and filter for high-confidence pairs only."""
        return [pair for pair in self.load_pairs() if pair.is_high_confidence]

    def clear_pairs(self) -> None:
        """Clear all stored pairs (both DB and file)."""
        try:
            from sqlalchemy import text

            from src.infrastructure.database import db

            instance_id = _get_instance_id()
            session = db.get_session()
            try:
                session.execute(
                    text("DELETE FROM cointegrated_pairs WHERE instance_id = :iid"),
                    {"iid": instance_id},
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        except Exception as exc:
            logger.debug(f"DB clear cointegrated pairs failed ({exc})")

        try:
            if self.storage_path.exists():
                self.storage_path.unlink()
                logger.info(f"Cleared pairs storage at {self.storage_path}")
        except Exception as e:
            logger.error(f"Error clearing pairs storage: {e}")


@dataclass(frozen=True)
class StoredPairScan:
    """The last pair scan a worker stored for one instance, as the table holds it.

    ``analyzed_at`` is the row's column value (a datetime on PostgreSQL; a plain
    string where the driver carries no type), ``timestamp`` the payload's own
    ISO stamp, and ``pairs`` the raw ``CointegrationResult`` dicts, unvalidated.
    """

    instance_id: str
    analyzed_at: Any
    timestamp: Optional[str]
    pairs: List[Dict[str, Any]]


def load_stored_pair_scan(
    session: "Session", instance_id: str
) -> Optional[StoredPairScan]:
    """Read the ``cointegrated_pairs`` row of any instance by id.

    :meth:`PairStorage.load_pairs` serves the running process's own
    ``BOT_INSTANCE_ID`` with a file fallback; this reads exactly one row for the
    id given and never touches the file system, so the API can show another
    worker's last scan. ``None`` when no scan is stored. The caller owns the
    session.
    """
    from sqlalchemy import text

    row = session.execute(
        text(
            "SELECT pairs_json, analyzed_at FROM cointegrated_pairs "
            "WHERE instance_id = :iid"
        ),
        {"iid": instance_id},
    ).fetchone()
    if row is None:
        return None
    data: Any = row[0]
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except ValueError:
            data = None
    payload: Dict[str, Any] = data if isinstance(data, dict) else {}
    raw_pairs = payload.get("pairs")
    pairs = (
        [pair for pair in raw_pairs if isinstance(pair, dict)]
        if isinstance(raw_pairs, list)
        else []
    )
    timestamp = payload.get("timestamp")
    return StoredPairScan(
        instance_id=instance_id,
        analyzed_at=row[1],
        timestamp=str(timestamp) if timestamp is not None else None,
        pairs=pairs,
    )


# Global instance for use throughout the application
pair_storage = PairStorage()

__all__ = [
    "CointegrationResult",
    "StoredPairScan",
    "calculate_confidence_score",
    "load_stored_pair_scan",
    "PairStorage",
    "pair_storage",
]
