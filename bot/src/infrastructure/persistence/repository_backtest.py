"""
Repository classes for backtest operations
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session


class BacktestRepository:
    """Repository for backtest operations"""

    _runs: Dict[int, Dict[str, Any]] = {}
    _next_id: int = 1

    def __init__(self, session: Session):
        self.session = session

    def _allocate_id(self) -> int:
        run_id = BacktestRepository._next_id
        BacktestRepository._next_id += 1
        return run_id

    def get_backtests(self) -> List[Dict[str, Any]]:
        """Get all backtests"""
        return sorted(
            BacktestRepository._runs.values(),
            key=lambda x: x.get("updated_at", ""),
            reverse=True,
        )

    def get_backtest_by_id(self, backtest_id: int) -> Optional[Dict[str, Any]]:
        """Get backtest by ID"""
        return BacktestRepository._runs.get(int(backtest_id))

    def create_backtest(self, config: dict) -> Dict[str, Any]:
        """Create a new backtest"""
        run_id = self._allocate_id()
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": run_id,
            "status": "created",
            "config": config,
            "created_at": now,
            "updated_at": now,
        }
        BacktestRepository._runs[run_id] = record
        return record

    def update_backtest_status(self, backtest_id: int, status: str) -> Optional[Dict[str, Any]]:
        """Update backtest status"""
        record = BacktestRepository._runs.get(int(backtest_id))
        if not record:
            return None
        record["status"] = status
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        return record
