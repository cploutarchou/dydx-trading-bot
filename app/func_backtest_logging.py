"""
Backtest logging utilities

Provides helper functions to log backtest execution events to the database.
Logs are created during backtest simulation and stored for real-time display.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_backtest_log(
    run_id: str, message: str, level: str = "info", db: Optional[Session] = None
) -> bool:
    """
    Create a log entry for backtest execution.

    Args:
        run_id: UUID of the backtest run
        message: Log message text
        level: Log level (debug, info, warning, error)
        db: SQLAlchemy database session

    Returns:
        True if log created successfully, False otherwise
    """
    if not db or not run_id:
        return False

    try:
        from backend.database import BacktestLog

        log_entry = BacktestLog(run_id_fk=run_id, message=message, level=level)
        db.add(log_entry)
        db.commit()
        return True

    except Exception as e:
        logger.warning("Failed to create backtest log: %s", e)
        return False


def log_backtest_info(run_id: str, message: str, db: Optional[Session] = None) -> bool:
    """Log info level message during backtest."""
    return create_backtest_log(run_id, message, "info", db)


def log_backtest_debug(run_id: str, message: str, db: Optional[Session] = None) -> bool:
    """Log debug level message during backtest."""
    return create_backtest_log(run_id, message, "debug", db)


def log_backtest_warning(
    run_id: str, message: str, db: Optional[Session] = None
) -> bool:
    """Log warning level message during backtest."""
    return create_backtest_log(run_id, message, "warning", db)


def log_backtest_error(run_id: str, message: str, db: Optional[Session] = None) -> bool:
    """Log error level message during backtest."""
    return create_backtest_log(run_id, message, "error", db)
