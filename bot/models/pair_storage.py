"""
Enhanced pair storage system for dYdX Trading Bot

Implements JSON-based storage with CSV backward compatibility,
following project patterns from config.py and bot_agents.json.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CointegrationResult:
    """
    Cointegration analysis result following project dataclass pattern.
    
    Attributes:
        base_market: Primary market symbol (e.g., 'BTC-USD')
        quote_market: Secondary market symbol (e.g., 'ETH-USD')
        hedge_ratio: Statistical hedge ratio for the pair
        half_life: Mean reversion half-life in hours
        zero_crossings: Number of Z-score zero crossings
        p_value: Statistical significance p-value
        z_score_mean: Historical Z-score mean
        z_score_std: Historical Z-score standard deviation
        analysis_timestamp: ISO timestamp of analysis
        confidence_score: Composite confidence metric (0-1)
    """
    base_market: str
    quote_market: str
    hedge_ratio: float
    half_life: float
    zero_crossings: int
    p_value: float
    z_score_mean: float = 0.0
    z_score_std: float = 1.0
    analysis_timestamp: str = ""
    confidence_score: float = 0.5

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'CointegrationResult':
        """Create instance from dictionary (JSON deserialization)."""
        return cls(**data)

    @property
    def pair_key(self) -> str:
        """Get unique key for this pair."""
        return f"{self.base_market}_{self.quote_market}"

    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high-confidence pair."""
        return self.confidence_score >= 0.7


class PairStorageManager:
    """
    Enhanced pair storage manager following singleton pattern like ConfigurationManager.
    
    Provides JSON-first storage with CSV backward compatibility and timestamped backups.
    Follows project patterns for file-based state persistence.
    """

    _instance: Optional['PairStorageManager'] = None

    def __new__(cls) -> 'PairStorageManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self.storage_path = Path("app")
        self.json_file = self.storage_path / "cointegrated_pairs.json"
        self.csv_file = self.storage_path / "cointegrated_pairs.csv"  # Legacy compatibility
        self.backup_dir = self.storage_path / "pair_history"

        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(exist_ok=True)

        self._initialized = True
        logger.info("PairStorageManager initialized with JSON primary storage")

    def save_pairs(self, pairs: List[CointegrationResult]) -> str:
        """
        Save pairs to JSON with CSV fallback for backward compatibility.
        
        Args:
            pairs: List of CointegrationResult objects to save
            
        Returns:
            Status string ("saved" for compatibility with existing code)
            
        Raises:
            Exception: If primary JSON storage fails
        """
        timestamp = datetime.now().isoformat()

        # Primary JSON storage (new format)
        data = {
            "metadata": {
                "analysis_timestamp": timestamp,
                "total_pairs": len(pairs),
                "version": "2.0",
                "bot_version": "dydx-trading-bot-enhanced",
                "high_confidence_count": len([p for p in pairs if p.is_high_confidence])
            },
            "pairs": [pair.to_dict() for pair in pairs]
        }

        try:
            with open(self.json_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(pairs)} pairs to JSON storage (v2.0)")
        except Exception as e:
            logger.error(f"Failed to save JSON pairs: {e}")
            raise

        # Legacy CSV compatibility (for existing workflows)
        try:
            if pairs:
                df = pd.DataFrame([pair.to_dict() for pair in pairs])
                df.to_csv(self.csv_file, index=False)
                logger.info(f"Maintained CSV compatibility with {len(pairs)} pairs")
        except Exception as e:
            logger.warning(f"CSV compatibility save failed: {e}")

        # Create timestamped backup (following project backup patterns)
        backup_file = self.backup_dir / f"pairs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(backup_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Created backup: {backup_file.name}")
        except Exception as e:
            logger.warning(f"Backup creation failed: {e}")

        # Clean up old backups
        self._cleanup_old_backups()

        return "saved"  # For compatibility with existing code

    def load_pairs(self) -> List[CointegrationResult]:
        """
        Load pairs with JSON-first, CSV fallback strategy.
        
        Returns:
            List of CointegrationResult objects
        """
        # Try JSON first (new format)
        if self.json_file.exists():
            try:
                with open(self.json_file, 'r') as f:
                    data = json.load(f)

                pairs = [CointegrationResult.from_dict(pair) for pair in data.get('pairs', [])]
                metadata = data.get('metadata', {})

                logger.info(
                    f"Loaded {len(pairs)} pairs from JSON storage "
                    f"(v{metadata.get('version', '1.0')}, "
                    f"{len([p for p in pairs if p.is_high_confidence])} high-confidence)"
                )
                return pairs

            except Exception as e:
                logger.warning(f"JSON loading failed: {e}, falling back to CSV")

        # Fallback to CSV (existing format for backward compatibility)
        if self.csv_file.exists():
            try:
                df = pd.read_csv(self.csv_file)
                pairs = []

                for _, row in df.iterrows():
                    pair = CointegrationResult(
                        base_market=str(row['base_market']),
                        quote_market=str(row['quote_market']),
                        hedge_ratio=float(row['hedge_ratio']),
                        half_life=float(row['half_life']),
                        zero_crossings=int(row.get('zero_crossings', 0)),
                        p_value=float(row.get('p_value', 0.0)),
                        z_score_mean=float(row.get('z_score_mean', 0.0)),
                        z_score_std=float(row.get('z_score_std', 1.0)),
                        analysis_timestamp=str(row.get('analysis_timestamp', '')),
                        confidence_score=float(row.get('confidence_score', 0.5))
                    )
                    pairs.append(pair)

                logger.info(f"Loaded {len(pairs)} pairs from CSV fallback")
                return pairs

            except Exception as e:
                logger.error(f"CSV loading failed: {e}")

        logger.warning("No pair storage found, returning empty list")
        return []

    def get_best_pairs(self, limit: int = 10) -> List[CointegrationResult]:
        """
        Get top pairs by confidence score.
        
        Args:
            limit: Maximum number of pairs to return
            
        Returns:
            List of highest-confidence pairs
        """
        pairs = self.load_pairs()
        sorted_pairs = sorted(pairs, key=lambda p: p.confidence_score, reverse=True)
        return sorted_pairs[:limit]

    def get_high_confidence_pairs(self) -> List[CointegrationResult]:
        """Get only high-confidence pairs (score >= 0.7)."""
        pairs = self.load_pairs()
        return [pair for pair in pairs if pair.is_high_confidence]

    def get_pair_by_markets(self, base_market: str, quote_market: str) -> Optional[CointegrationResult]:
        """
        Get specific pair by market symbols.
        
        Args:
            base_market: Base market symbol
            quote_market: Quote market symbol
            
        Returns:
            CointegrationResult if found, None otherwise
        """
        pairs = self.load_pairs()
        for pair in pairs:
            if pair.base_market == base_market and pair.quote_market == quote_market:
                return pair
        return None

    def get_storage_info(self) -> Dict:
        """Get information about current storage state."""
        pairs = self.load_pairs()

        return {
            "total_pairs": len(pairs),
            "high_confidence_pairs": len([p for p in pairs if p.is_high_confidence]),
            "storage_format": "JSON" if self.json_file.exists() else "CSV",
            "has_json": self.json_file.exists(),
            "has_csv": self.csv_file.exists(),
            "backup_count": len(list(self.backup_dir.glob("pairs_*.json"))),
            "last_analysis": pairs[0].analysis_timestamp if pairs else None
        }

    def _cleanup_old_backups(self, keep_days: int = 7) -> None:
        """Clean up old backup files."""
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 3600)

        cleaned = 0
        for backup_file in self.backup_dir.glob("pairs_*.json"):
            try:
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
                    cleaned += 1
            except Exception as e:
                logger.warning(f"Failed to clean backup {backup_file.name}: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old backup files")


def calculate_confidence_score(p_value: float, half_life: float, zero_crossings: int) -> float:
    """
    Calculate composite confidence score following project's analytical approach.
    
    Args:
        p_value: Statistical significance p-value
        half_life: Mean reversion half-life in hours
        zero_crossings: Number of Z-score zero crossings
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    # Statistical significance (higher weight for lower p-value)
    p_score = max(0, 1 - (p_value / 0.05)) * 0.5

    # Mean reversion speed (prefer shorter half-lives up to 24h)
    half_life_score = max(0, 1 - (half_life / 24)) * 0.3

    # Trading frequency potential (more crossings = better)
    crossing_score = min(1, zero_crossings / 10) * 0.2

    confidence = p_score + half_life_score + crossing_score
    return min(1.0, max(0.0, confidence))


# Singleton instance following project pattern
pair_storage = PairStorageManager()
