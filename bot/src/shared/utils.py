"""Utility functions for trading bot."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict


def format_number(curr_num: Any, match_num: Any) -> str:
    """
    Format a number to match the decimal places of another number.

    Args:
        curr_num: Number to format
        match_num: Number with desired decimal format

    Returns:
        Formatted string representation
    """
    curr_num_string = f"{curr_num}"
    match_num_string = f"{match_num}"

    if "." in match_num_string:
        match_decimals = len(match_num_string.split(".")[1])
        curr_num_string = f"{curr_num:.{match_decimals}f}"
        return curr_num_string
    else:
        return f"{int(curr_num)}"


def format_time(timestamp: datetime) -> str:
    """Format timestamp to ISO 8601 UTC string with Z suffix and no microseconds."""
    return (
        timestamp.replace(microsecond=0)
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def get_ISO_times() -> Dict[str, Dict[str, str]]:
    """
    Get ISO time ranges for historical data queries.

    Returns four 100-hour windows of time ranges for market data.

    Returns:
        Dictionary with time ranges for historical data retrieval
    """
    # Get timestamps
    date_start_0 = datetime.now(timezone.utc)
    date_start_1 = date_start_0 - timedelta(hours=100)
    date_start_2 = date_start_1 - timedelta(hours=100)
    date_start_3 = date_start_2 - timedelta(hours=100)
    date_start_4 = date_start_3 - timedelta(hours=100)

    # Format datetimes
    times_dict = {
        "range_1": {
            "from_iso": format_time(date_start_1),
            "to_iso": format_time(date_start_0),
        },
        "range_2": {
            "from_iso": format_time(date_start_2),
            "to_iso": format_time(date_start_1),
        },
        "range_3": {
            "from_iso": format_time(date_start_3),
            "to_iso": format_time(date_start_2),
        },
        "range_4": {
            "from_iso": format_time(date_start_4),
            "to_iso": format_time(date_start_3),
        },
    }

    # Return result
    return times_dict
