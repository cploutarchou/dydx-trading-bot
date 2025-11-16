"""
Pair storage models and persistence layer for cointegration analysis results.

This module provides data structures and utilities for storing and retrieving
cointegration analysis results, including enhanced metrics and confidence scoring.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


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
    creation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def is_high_confidence(self) -> bool:
        """Returns True if confidence score is above threshold (0.7)."""
        return self.confidence_score >= 0.7

    @property
    def pair_name(self) -> str:
        """Returns formatted pair name."""
        return f"{self.base_market}_{self.quote_market}"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CointegrationResult":
        """Create instance from dictionary."""
        return cls(**data)


def calculate_confidence_score(
    p_value: float,
    half_life: float,
    zero_crossings: int,
    max_half_life: float = 14.0,
    min_zero_crossings: int = 5
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


class PairStorage:
    """
    Manages persistence of cointegration analysis results.

    Handles saving and loading cointegrated pairs with enhanced metrics
    to a JSON-based storage system.
    """

    def __init__(self, storage_path: str = "pair_history/cointegration_results.json"):
        """
        Initialize pair storage.

        Args:
            storage_path: Path to JSON storage file
        """
        self.storage_path = Path(storage_path)
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        """Ensure a storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def save_pairs(self, pairs: List[CointegrationResult]) -> dict:
        """
        Save cointegration results to storage.

        Args:
            pairs: List of CointegrationResult objects

        Returns:
            dict: Result metadata including number of pairs saved
        """
        try:
            # Convert to list of dictionaries for JSON serialization
            pairs_data = [pair.to_dict() for pair in pairs]

            # Add metadata
            storage_data = {
                "timestamp": datetime.now().isoformat(),
                "total_pairs": len(pairs),
                "high_confidence_pairs": len([p for p in pairs if p.is_high_confidence]),
                "pairs": pairs_data
            }

            # Write to file
            with open(self.storage_path, 'w') as f:
                json.dump(storage_data, f, indent=2)

            logger.info(f"Saved {len(pairs)} cointegration results to {self.storage_path}")

            return {
                "success": True,
                "pairs_saved": len(pairs),
                "high_confidence": len([p for p in pairs if p.is_high_confidence]),
                "path": str(self.storage_path)
            }

        except Exception as e:
            logger.error(f"Error saving pairs to {self.storage_path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def load_pairs(self) -> List[CointegrationResult]:
        """
        Load cointegration results from storage.

        Returns:
            List of CointegrationResult objects, or empty list if file doesn't exist
        """
        try:
            if not self.storage_path.exists():
                logger.debug(f"No pairs file found at {self.storage_path}")
                return []

            with open(self.storage_path, 'r') as f:
                storage_data = json.load(f)

            # Convert dictionaries to CointegrationResult objects
            pairs = [
                CointegrationResult.from_dict(pair_data)
                for pair_data in storage_data.get("pairs", [])
            ]

            logger.info(f"Loaded {len(pairs)} cointegration results from {self.storage_path}")
            return pairs

        except Exception as e:
            logger.error(f"Error loading pairs from {self.storage_path}: {e}")
            return []

    def get_high_confidence_pairs(self) -> List[CointegrationResult]:
        """
        Load and filter for high-confidence pairs only.

        Returns:
            List of high-confidence CointegrationResult objects
        """
        all_pairs = self.load_pairs()
        return [pair for pair in all_pairs if pair.is_high_confidence]

    def clear_pairs(self):
        """Clear all stored pairs."""
        try:
            if self.storage_path.exists():
                self.storage_path.unlink()
                logger.info(f"Cleared pairs storage at {self.storage_path}")
        except Exception as e:
            logger.error(f"Error clearing pairs storage: {e}")


# Global instance for use throughout the application
pair_storage = PairStorage()

__all__ = [
    "CointegrationResult",
    "calculate_confidence_score",
    "PairStorage",
    "pair_storage",
]

