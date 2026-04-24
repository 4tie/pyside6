"""Service for reading and parsing OHLCV candle data metadata."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.parsing.json_parser import parse_json_file
from app.core.utils.app_logger import get_logger

_log = get_logger("services.data_status")

# Candles older than this many days are considered stale
_STALE_DAYS = 3

# Timeframe → expected seconds between candles
_TF_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800,
    "12h": 43200, "1d": 86400, "3d": 259200, "1w": 604800,
}


class DataStatusService:
    """Service for reading candle metadata from OHLCV JSON files."""

    @staticmethod
    def read_candle_meta(path: Path, tf: str) -> Optional[dict]:
        """
        Read a freqtrade OHLCV JSON file and return metadata:
          first_ts, last_ts, candle_count, gap_count, stale
        Returns None if file is unreadable or empty.
        """
        try:
            raw = parse_json_file(path)
            if not raw or not isinstance(raw, list):
                return None

            # Each candle: [timestamp_ms, open, high, low, close, volume]
            timestamps = [c[0] for c in raw if isinstance(c, list) and len(c) >= 1]
            if not timestamps:
                return None

            timestamps.sort()
            first_ts = timestamps[0]
            last_ts  = timestamps[-1]
            count    = len(timestamps)

            # Detect gaps: consecutive candles more than 2× expected interval apart
            expected = _TF_SECONDS.get(tf, 300) * 1000  # ms
            gaps = sum(
                1 for a, b in zip(timestamps, timestamps[1:])
                if (b - a) > expected * 2
            )

            stale = DataStatusService._days_ago(last_ts) > _STALE_DAYS

            return {
                "first_ts": first_ts,
                "last_ts":  last_ts,
                "count":    count,
                "gaps":     gaps,
                "stale":    stale,
                "days_ago": DataStatusService._days_ago(last_ts),
            }
        except Exception as e:
            _log.warning("Could not read %s: %s", path.name, e)
            return None

    @staticmethod
    def format_timestamp(ts_ms: int) -> str:
        """Format a millisecond timestamp to a readable date string."""
        try:
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "?"

    @staticmethod
    def _days_ago(ts_ms: int) -> float:
        """Return how many days ago a millisecond timestamp was."""
        now_ms = datetime.now(tz=timezone.utc).timestamp() * 1000
        return (now_ms - ts_ms) / (1000 * 86400)
