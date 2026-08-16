"""DataFrame memory management and cleanup utilities."""

import contextlib
import gc
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

# Memory tracking for DataFrames
_dataframe_registry: Dict[str, Dict[str, Any]] = {}
_registry_lock = threading.Lock()
_max_tracked_frames = 100
_tracking_enabled = True


def enable_dataframe_tracking(enabled: bool = True):
    """Enable or disable DataFrame memory tracking."""
    global _tracking_enabled
    _tracking_enabled = enabled
    logger.info(f"DataFrame tracking {'enabled' if enabled else 'disabled'}")


def register_dataframe(
    df: Any, name: str, metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Register a DataFrame for memory tracking.

    Args:
        df: pandas DataFrame to track
        name: Descriptive name for the DataFrame
        metadata: Optional metadata about the DataFrame

    Returns:
        Unique ID for the registered DataFrame
    """
    if not _tracking_enabled:
        return ""

    try:
        frame_id = f"{name}_{id(df)}"
        frame_size = get_dataframe_memory_usage(df)

        entry = {
            "id": frame_id,
            "name": name,
            "size_bytes": frame_size,
            "size_mb": frame_size / (1024 * 1024),
            "rows": len(df) if hasattr(df, "__len__") else 0,
            "columns": len(df.columns) if hasattr(df, "columns") else 0,
            "created_at": datetime.now(),
            "metadata": metadata or {},
            "df": df,  # Keep reference to prevent garbage collection
        }

        with _registry_lock:
            # Clean up old entries if registry is too large
            if len(_frame_registry) > _max_tracked_frames:
                _cleanup_old_entries()

            _frame_registry[frame_id] = entry

        logger.debug(f"Registered DataFrame {frame_id}: {entry['size_mb']:.2f} MB")
        return frame_id

    except Exception as e:
        logger.warning(f"Failed to register DataFrame {name}: {e}")
        return ""


def unregister_dataframe(frame_id: str) -> bool:
    """Unregister a DataFrame from tracking and cleanup memory.

    Args:
        frame_id: ID returned by register_dataframe

    Returns:
        True if successfully unregistered
    """
    if not frame_id or not _tracking_enabled:
        return False

    try:
        with _registry_lock:
            entry = _frame_registry.pop(frame_id, None)
            if entry:
                df = entry.get("df")
                if df is not None:
                    # Explicit cleanup
                    cleanup_dataframe(df)
                logger.debug(
                    f"Unregistered DataFrame {frame_id}: {entry['size_mb']:.2f} MB freed"
                )
                return True
        return False
    except Exception as e:
        logger.warning(f"Failed to unregister DataFrame {frame_id}: {e}")
        return False


def get_dataframe_memory_usage(df: Any) -> int:
    """Get approximate memory usage of a DataFrame in bytes.

    Args:
        df: pandas DataFrame or similar object

    Returns:
        Memory usage in bytes
    """
    try:
        if hasattr(df, "memory_usage"):
            return df.memory_usage(deep=True).sum()
        elif hasattr(df, "nbytes"):
            return df.nbytes
        elif hasattr(df, "__sizeof__"):
            return df.__sizeof__()
        else:
            return 0
    except Exception:
        return 0


def cleanup_dataframe(df: Any) -> bool:
    """Clean up a DataFrame to free memory.

    Args:
        df: pandas DataFrame or similar object to cleanup

    Returns:
        True if cleanup was successful
    """
    try:
        if df is None:
            return False

        # Clear DataFrame contents
        if hasattr(df, "columns"):
            # Drop columns to free memory
            df.drop(columns=list(df.columns), inplace=True, errors="ignore")

        # Delete the object reference
        del df

        # Force garbage collection
        gc.collect()

        return True

    except Exception as e:
        logger.warning(f"Failed to cleanup DataFrame: {e}")
        return False


def _cleanup_old_entries():
    """Clean up old entries from the DataFrame registry."""
    try:
        cutoff_time = datetime.now() - timedelta(minutes=30)
        to_remove = []

        for frame_id, entry in _frame_registry.items():
            if entry["created_at"] < cutoff_time:
                to_remove.append(frame_id)

        for frame_id in to_remove:
            if frame_id in _frame_registry:
                entry = _frame_registry.pop(frame_id)
                cleanup_dataframe(entry.get("df"))

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old DataFrame registry entries")

    except Exception as e:
        logger.warning(f"Failed to cleanup old registry entries: {e}")


@contextlib.contextmanager
def managed_dataframe(df: Any, name: str, metadata: Optional[Dict[str, Any]] = None):
    """Context manager for automatic DataFrame cleanup.

    Args:
        df: pandas DataFrame to manage
        name: Descriptive name for tracking
        metadata: Optional metadata about the DataFrame

    Yields:
        The managed DataFrame

    Example:
        with managed_dataframe(large_df, "backtest_results") as df:
            # Process data
            results = process(df)
        # DataFrame automatically cleaned up here
    """
    frame_id = None
    try:
        frame_id = register_dataframe(df, name, metadata)
        yield df
    finally:
        if frame_id:
            unregister_dataframe(frame_id)


def get_memory_summary() -> Dict[str, Any]:
    """Get summary of tracked DataFrame memory usage.

    Returns:
        Dictionary with memory statistics
    """
    try:
        with _registry_lock:
            if not _frame_registry:
                return {
                    "tracked_dataframes": 0,
                    "total_memory_mb": 0.0,
                    "largest_frame_mb": 0.0,
                    "oldest_frame_minutes": 0.0,
                }

            total_memory = sum(
                entry["size_bytes"] for entry in _frame_registry.values()
            )
            largest = max(_frame_registry.values(), key=lambda x: x["size_bytes"])
            oldest = min(_frame_registry.values(), key=lambda x: x["created_at"])
            oldest_age = (datetime.now() - oldest["created_at"]).total_seconds() / 60

            return {
                "tracked_dataframes": len(_frame_registry),
                "total_memory_mb": total_memory / (1024 * 1024),
                "largest_frame_mb": largest["size_bytes"] / (1024 * 1024),
                "largest_frame_name": largest["name"],
                "oldest_frame_minutes": oldest_age,
                "oldest_frame_name": oldest["name"],
            }

    except Exception as e:
        logger.error(f"Failed to get memory summary: {e}")
        return {"error": str(e)}


def force_cleanup_all():
    """Force cleanup of all tracked DataFrames."""
    try:
        # Snapshot ids under the lock, then unregister outside it —
        # unregister_dataframe acquires the same (non-reentrant) lock, so
        # calling it while holding the lock deadlocks the worker thread.
        with _registry_lock:
            frame_ids = list(_frame_registry.keys())
        cleaned = 0

        for frame_id in frame_ids:
            if unregister_dataframe(frame_id):
                cleaned += 1

        logger.info(f"Force cleanup completed: {cleaned}/{len(frame_ids)} DataFrames")
        return cleaned

    except Exception as e:
        logger.error(f"Failed to force cleanup: {e}")
        return 0


def optimize_dataframe_memory(df: Any) -> Any:
    """Optimize DataFrame memory usage by downcasting data types.

    Args:
        df: pandas DataFrame to optimize

    Returns:
        Optimized DataFrame
    """
    try:
        if df is None or not hasattr(df, "dtypes"):
            return df

        # Make a copy to avoid modifying original
        optimized = df.copy()

        # Downcast numeric columns
        for col in optimized.columns:
            dtype = optimized[col].dtype
            if dtype == "int64":
                optimized[col] = optimized[col].astype("int32")
            elif dtype == "float64":
                optimized[col] = optimized[col].astype("float32")
            elif dtype == "object":
                # Try to convert to categorical if many duplicates
                unique_ratio = optimized[col].nunique() / len(optimized[col])
                if unique_ratio < 0.5:  # If less than 50% unique values
                    optimized[col] = optimized[col].astype("category")

        memory_before = get_dataframe_memory_usage(df)
        memory_after = get_dataframe_memory_usage(optimized)
        saved_percent = (
            ((memory_before - memory_after) / memory_before * 100)
            if memory_before > 0
            else 0
        )

        logger.debug(f"DataFrame memory optimization: {saved_percent:.1f}% reduction")
        return optimized

    except Exception as e:
        logger.warning(f"DataFrame optimization failed: {e}")
        return df


def cleanup_cache_entries(
    cache_dict: Dict[str, Any], max_size: int = 100, max_age_minutes: int = 60
):
    """Clean up cache entries with size and age limits.

    Args:
        cache_dict: Dictionary containing cache entries
        max_size: Maximum number of entries to keep
        max_age_minutes: Maximum age of entries in minutes
    """
    try:
        current_time = time.monotonic()
        cutoff_time = current_time - (max_age_minutes * 60)

        # Find entries to remove
        entries_to_remove = []

        # Remove by age
        for key, value in cache_dict.items():
            if isinstance(value, dict) and "expires" in value:
                if value["expires"] < cutoff_time:
                    entries_to_remove.append(key)
            elif isinstance(value, dict) and "created_at" in value:
                created_time = value["created_at"]
                if isinstance(created_time, datetime):
                    if (current_time - created_time.timestamp()) > (
                        max_age_minutes * 60
                    ):
                        entries_to_remove.append(key)

        # Remove oldest entries if still too large
        if len(cache_dict) - len(entries_to_remove) > max_size:
            # Sort by expiration time and remove oldest
            sorted_entries = sorted(
                [
                    (k, v)
                    for k, v in cache_dict.items()
                    if k not in entries_to_remove and isinstance(v, dict)
                ],
                key=lambda x: x[1].get("expires", 0),
            )
            excess = len(cache_dict) - len(entries_to_remove) - max_size
            for i in range(excess):
                entries_to_remove.append(sorted_entries[i][0])

        # Remove entries and cleanup DataFrames
        for key in entries_to_remove:
            if key in cache_dict:
                entry = cache_dict[key]
                # Cleanup any DataFrame references
                if isinstance(entry, dict):
                    if "data" in entry:
                        cleanup_dataframe(entry["data"])
                    elif isinstance(entry, dict) and "df" in entry:
                        cleanup_dataframe(entry["df"])
                del cache_dict[key]

        if entries_to_remove:
            logger.info(f"Cache cleanup: removed {len(entries_to_remove)} entries")

    except Exception as e:
        logger.warning(f"Cache cleanup failed: {e}")


# Global DataFrame registry
_frame_registry: Dict[str, Dict[str, Any]] = {}


def get_dataframe_cleanup_stats() -> Dict[str, Any]:
    """Get statistics about DataFrame cleanup operations."""
    return {
        "tracking_enabled": _tracking_enabled,
        "tracked_count": len(_frame_registry),
        "max_tracked": _max_tracked_frames,
        "registry_size_kb": _get_registry_size(),
        **get_memory_summary(),
    }


def _get_registry_size() -> float:
    """Get approximate size of the registry in KB."""
    try:
        import sys

        return sys.getsizeof(_frame_registry) / 1024
    except Exception:
        return 0.0
