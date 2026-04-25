"""
QAbstractTableModel for the Strategy Optimizer trial list.

Displays one row per TrialRecord with columns:
  #, Params, Profit %, DD %, Score, ★

Supports:
- Incremental row insertion via beginInsertRows/endInsertRows (no full reset)
- Targeted dataChanged emission for the ★ column when best changes
- In-memory sort by any numeric column
- DisplayRole, BackgroundRole (semantic row colors), and UserRole (full TrialRecord)
"""
from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from app.core.models.optimizer_models import TrialRecord, TrialStatus
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.widgets.trial_table_model")

# ── Row background colors (applied via BackgroundRole, not stylesheets) ──────
_COLOR_BEST_BG    = QColor("#1E3A2F")   # muted green — Accepted_Best row
_COLOR_BEST_STAR  = QColor("#4CAF50")   # bright green star
_COLOR_FAILED_BG  = QColor("#3A1E1E")   # muted red — failed trial
_COLOR_RUNNING_BG = QColor("#1E2A3A")   # soft blue — running trial
_COLOR_DEFAULT_BG = QColor("#1E1E1E")   # standard dark background

# Column index constants
_COL_NUMBER = 0
_COL_PARAMS = 1
_COL_PROFIT = 2
_COL_DD     = 3
_COL_SCORE  = 4
_COL_STAR   = 5


def _format_params(record: TrialRecord) -> str:
    """Return a compact string of up to 3 key=value pairs from candidate_params."""
    if not record.candidate_params:
        return "—"
    items = list(record.candidate_params.items())[:3]
    parts = []
    for k, v in items:
        if isinstance(v, float):
            parts.append(f"{k}={v:.4g}")
        else:
            parts.append(f"{k}={v}")
    suffix = ", …" if len(record.candidate_params) > 3 else ""
    return ", ".join(parts) + suffix


class TrialTableModel(QAbstractTableModel):
    """
    QAbstractTableModel backed by an in-memory list of TrialRecord objects.

    Thread safety: all mutations must happen on the Qt main thread.
    The OptimizerPage bridges background-thread callbacks to the main thread
    via Qt signals before calling append_trial() or update_best().
    """

    COLUMNS: List[str] = ["#", "Params", "Profit %", "DD %", "Score", "★"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: List[TrialRecord] = []

    # ── QAbstractTableModel interface ─────────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> Any:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # noqa: N802
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._records):
            return None

        record = self._records[row]

        # ── UserRole: return the full TrialRecord for the detail panel ────────
        if role == Qt.UserRole:
            return record

        # ── BackgroundRole: semantic row colors ───────────────────────────────
        if role == Qt.BackgroundRole:
            if record.is_best:
                return _COLOR_BEST_BG
            if record.status == TrialStatus.FAILED:
                return _COLOR_FAILED_BG
            if record.status == TrialStatus.RUNNING:
                return _COLOR_RUNNING_BG
            return _COLOR_DEFAULT_BG

        # ── ForegroundRole: star column gets a bright green for best row ──────
        if role == Qt.ForegroundRole:
            if col == _COL_STAR and record.is_best:
                return _COLOR_BEST_STAR

        # ── DisplayRole ───────────────────────────────────────────────────────
        if role == Qt.DisplayRole:
            return self._display_value(record, col)

        # ── TextAlignmentRole: right-align numeric columns ────────────────────
        if role == Qt.TextAlignmentRole:
            if col in (_COL_NUMBER, _COL_PROFIT, _COL_DD, _COL_SCORE, _COL_STAR):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)

        return None

    # ── Public mutation API ───────────────────────────────────────────────────

    def append_trial(self, record: TrialRecord) -> None:
        """
        Append a new TrialRecord to the model using beginInsertRows/endInsertRows.
        No full model reset — only the new row is signalled to views.
        """
        row = len(self._records)
        self.beginInsertRows(QModelIndex(), row, row)
        self._records.append(record)
        self.endInsertRows()
        _log.debug("Appended trial #%d (status=%s)", record.trial_number, record.status)

    def update_trial(self, record: TrialRecord) -> None:
        """
        Replace an existing record in-place (e.g. when a RUNNING trial completes).
        Emits dataChanged for the entire row.
        """
        idx = self._index_of(record.trial_number)
        if idx < 0:
            _log.warning(
                "update_trial: trial #%d not found — appending instead",
                record.trial_number,
            )
            self.append_trial(record)
            return
        self._records[idx] = record
        tl = self.index(idx, 0)
        br = self.index(idx, len(self.COLUMNS) - 1)
        self.dataChanged.emit(tl, br, [Qt.DisplayRole, Qt.BackgroundRole])

    def update_best(self, old_best_trial_number: int, new_best_trial_number: int) -> None:
        """
        Update the is_best flag on the affected records and emit dataChanged
        only for the ★ column of the two affected rows.

        Parameters
        ----------
        old_best_trial_number:
            Trial number that was previously the best (0 or negative = none).
        new_best_trial_number:
            Trial number that is now the best.
        """
        star_col = self.COLUMNS.index("★")

        # Clear old best
        old_idx = self._index_of(old_best_trial_number)
        if old_idx >= 0:
            self._records[old_idx] = self._records[old_idx].model_copy(
                update={"is_best": False}
            )
            tl = self.index(old_idx, star_col)
            self.dataChanged.emit(tl, tl, [Qt.DisplayRole, Qt.BackgroundRole, Qt.ForegroundRole])

        # Mark new best
        new_idx = self._index_of(new_best_trial_number)
        if new_idx >= 0:
            self._records[new_idx] = self._records[new_idx].model_copy(
                update={"is_best": True}
            )
            tl = self.index(new_idx, star_col)
            self.dataChanged.emit(tl, tl, [Qt.DisplayRole, Qt.BackgroundRole, Qt.ForegroundRole])

        _log.debug(
            "update_best: old=#%d (row=%d) → new=#%d (row=%d)",
            old_best_trial_number, old_idx,
            new_best_trial_number, new_idx,
        )

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:  # noqa: N802
        """
        Sort the in-memory records by the given column without reloading from disk.

        Numeric columns (#, Profit %, DD %, Score) are sorted by their float value.
        Non-numeric columns (Params, ★) fall back to string sort.
        """
        if not self._records:
            return

        reverse = order == Qt.DescendingOrder

        def sort_key(record: TrialRecord) -> Any:
            if column == _COL_NUMBER:
                return record.trial_number
            if column == _COL_PROFIT:
                return _safe_float(
                    record.metrics.total_profit_pct if record.metrics else None
                )
            if column == _COL_DD:
                return _safe_float(
                    record.metrics.max_drawdown_pct if record.metrics else None
                )
            if column == _COL_SCORE:
                return _safe_float(record.score)
            if column == _COL_STAR:
                return 1 if record.is_best else 0
            # Params column — sort by string representation
            return _format_params(record)

        self.layoutAboutToBeChanged.emit()
        self._records.sort(key=sort_key, reverse=reverse)
        self.layoutChanged.emit()

    def clear(self) -> None:
        """Remove all records from the model."""
        self.beginResetModel()
        self._records.clear()
        self.endResetModel()

    def record_at(self, row: int) -> Optional[TrialRecord]:
        """Return the TrialRecord at the given row index, or None if out of range."""
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    # ── Private helpers ───────────────────────────────────────────────────────

    def _index_of(self, trial_number: int) -> int:
        """Return the row index for the given trial_number, or -1 if not found."""
        for i, r in enumerate(self._records):
            if r.trial_number == trial_number:
                return i
        return -1

    def _display_value(self, record: TrialRecord, col: int) -> str:
        """Return the display string for a given record and column."""
        if col == _COL_NUMBER:
            return str(record.trial_number)

        if col == _COL_PARAMS:
            return _format_params(record)

        if col == _COL_PROFIT:
            if record.status == TrialStatus.FAILED:
                return "FAIL"
            if record.metrics is None:
                return "—"
            return f"{record.metrics.total_profit_pct:.2f}%"

        if col == _COL_DD:
            if record.status == TrialStatus.FAILED:
                return "—"
            if record.metrics is None:
                return "—"
            return f"{record.metrics.max_drawdown_pct:.1f}%"

        if col == _COL_SCORE:
            if record.status == TrialStatus.FAILED:
                return "—"
            if record.score is None:
                return "—"
            return f"{record.score:.4g}"

        if col == _COL_STAR:
            return "★" if record.is_best else ""

        return ""


# ── Utility ───────────────────────────────────────────────────────────────────

def _safe_float(value: Any, fallback: float = float("-inf")) -> float:
    """Convert value to float for sorting; returns fallback on failure."""
    if value is None:
        return fallback
    try:
        import math
        f = float(value)
        return f if math.isfinite(f) else fallback
    except (TypeError, ValueError):
        return fallback
