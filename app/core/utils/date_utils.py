from datetime import datetime, timedelta


def calculate_timerange_preset(preset: str) -> str:
    """Convert preset name to YYYYMMDD-YYYYMMDD timerange.

    Args:
        preset: One of 7d, 14d, 30d, 90d, 120d, 360d

    Returns:
        Timerange string like "20260308-20260415" (start_date-end_date)

    Example:
        >>> calculate_timerange_preset("30d")
        "20260316-20260415"  # approximately (depends on current date)
    """
    days_map = {
        "7d": 7,
        "14d": 14,
        "30d": 30,
        "90d": 90,
        "120d": 120,
        "360d": 360,
    }

    n_days = days_map.get(preset, 30)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_days)

    return f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
