"""
Bug condition exploration test for Bug 3: IS/OOS Split Verification.

This test encodes the EXPECTED (correct) behavior and verifies the current
IS/OOS split implementation. According to the design document, the current
implementation appears correct, so this test may PASS on unfixed code.

Bug 3 — Boundary day handling in IS/OOS split

The test verifies:
- compute_in_sample_timerange() ends at oos_start - 1 day
- compute_oos_timerange() starts at oos_start
- Boundary day is included in OOS and excluded from IS
- No gap exists between IS and OOS ranges

**Validates: Requirements 1.4, 1.5, 1.6, 2.5, 2.6, 2.7**
"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from app.core.services.loop_service import LoopService
from app.core.services.improve_service import ImproveService
from app.core.models.loop_models import LoopConfig

from hypothesis import given, settings as h_settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loop_service() -> LoopService:
    """Create a LoopService with a mocked ImproveService."""
    improve_mock = MagicMock(spec=ImproveService)
    return LoopService(improve_mock)


def _make_loop_config(
    date_from: str,
    date_to: str,
    oos_split_pct: float = 20.0,
    strategy: str = "TestStrategy"
) -> LoopConfig:
    """Return a minimal LoopConfig for testing."""
    return LoopConfig(
        strategy=strategy,
        timeframe="5m",
        max_iterations=5,
        target_profit_pct=5.0,
        target_win_rate=55.0,
        target_max_drawdown=20.0,
        target_min_trades=30,
        date_from=date_from,
        date_to=date_to,
        oos_split_pct=oos_split_pct,
    )


def _parse_timerange(timerange: str) -> tuple[datetime, datetime]:
    """Parse a timerange string like '20240101-20240131' into start and end dates."""
    if not timerange or "-" not in timerange:
        raise ValueError(f"Invalid timerange: {timerange}")
    
    start_str, end_str = timerange.split("-")
    start_date = datetime.strptime(start_str, "%Y%m%d")
    end_date = datetime.strptime(end_str, "%Y%m%d")
    return start_date, end_date


def _compute_oos_start(date_from: datetime, date_to: datetime, oos_split_pct: float) -> datetime:
    """Compute the OOS start date using the same logic as LoopService."""
    total_days = (date_to - date_from).days
    oos_days = max(1, int(total_days * oos_split_pct / 100.0))
    oos_start = date_to - timedelta(days=oos_days)
    return oos_start


# ---------------------------------------------------------------------------
# Bug condition exploration tests
# ---------------------------------------------------------------------------

@pytest.mark.bug_condition
@given(
    # Generate date ranges with at least 10 days to ensure meaningful splits
    days_total=st.integers(min_value=10, max_value=365),
    oos_split_pct=st.floats(min_value=10.0, max_value=50.0),
)
@h_settings(max_examples=50, deadline=None)
def test_bug_condition_is_oos_split_no_gap(days_total, oos_split_pct):
    """
    **Property 1: Bug Condition** - IS/OOS Split Verification
    
    Bug condition: isBugCondition3(input) where:
      - input.oos_start_date EXISTS
      - input.in_sample_end_date == (input.oos_start_date - 1 day)
      - input.oos_start_date == input.oos_start_date
      - boundary_day_excluded_from_both_ranges(input) OR boundary_day_in_both_ranges(input)
    
    This test verifies that the IS/OOS split is correct:
    - IS ends at oos_start - 1 day
    - OOS starts at oos_start
    - Boundary day is included in OOS and excluded from IS
    - No gap exists between the two ranges
    
    EXPECTED OUTCOME on unfixed code: MAY PASS
      The current implementation appears correct based on code review.
      If this test passes, it confirms Bug 3 does not exist.
      
    EXPECTED OUTCOME after fix: PASS
      The split is correct with no gap and proper boundary handling.
    
    **Validates: Requirements 1.4, 1.5, 1.6, 2.5, 2.6, 2.7**
    """
    # Create date range
    date_from = datetime(2024, 1, 1)
    date_to = date_from + timedelta(days=days_total)
    
    # Ensure we have enough days for a meaningful split
    assume(days_total > 2)
    
    # Create config
    config = _make_loop_config(
        date_from=date_from.strftime("%Y%m%d"),
        date_to=date_to.strftime("%Y%m%d"),
        oos_split_pct=oos_split_pct,
    )
    
    # Create LoopService and compute timeranges
    loop_service = _make_loop_service()
    is_timerange = loop_service.compute_in_sample_timerange(config)
    oos_timerange = loop_service.compute_oos_timerange(config)
    
    # Skip if either timerange is empty
    assume(is_timerange and oos_timerange)
    assume("-" in is_timerange and "-" in oos_timerange)
    
    # Parse the timeranges
    is_start, is_end = _parse_timerange(is_timerange)
    oos_start, oos_end = _parse_timerange(oos_timerange)
    
    # Compute expected oos_start using the same logic as LoopService
    expected_oos_start = _compute_oos_start(date_from, date_to, oos_split_pct)
    
    # Property 1: IS should end at oos_start - 1 day
    expected_is_end = expected_oos_start - timedelta(days=1)
    assert is_end == expected_is_end, (
        f"Bug 3 detected: IS end date is incorrect.\n"
        f"Date range: {date_from.strftime('%Y%m%d')} to {date_to.strftime('%Y%m%d')} ({days_total} days)\n"
        f"OOS split: {oos_split_pct}%\n"
        f"Expected OOS start: {expected_oos_start.strftime('%Y%m%d')}\n"
        f"Expected IS end: {expected_is_end.strftime('%Y%m%d')} (oos_start - 1 day)\n"
        f"Actual IS end: {is_end.strftime('%Y%m%d')}\n"
        f"IS timerange: {is_timerange}\n"
        f"OOS timerange: {oos_timerange}\n"
    )
    
    # Property 2: OOS should start at oos_start
    assert oos_start == expected_oos_start, (
        f"Bug 3 detected: OOS start date is incorrect.\n"
        f"Date range: {date_from.strftime('%Y%m%d')} to {date_to.strftime('%Y%m%d')} ({days_total} days)\n"
        f"OOS split: {oos_split_pct}%\n"
        f"Expected OOS start: {expected_oos_start.strftime('%Y%m%d')}\n"
        f"Actual OOS start: {oos_start.strftime('%Y%m%d')}\n"
        f"IS timerange: {is_timerange}\n"
        f"OOS timerange: {oos_timerange}\n"
    )
    
    # Property 3: No gap between IS and OOS (IS end + 1 day == OOS start)
    gap_days = (oos_start - is_end).days
    assert gap_days == 1, (
        f"Bug 3 detected: Gap or overlap between IS and OOS ranges.\n"
        f"Date range: {date_from.strftime('%Y%m%d')} to {date_to.strftime('%Y%m%d')} ({days_total} days)\n"
        f"OOS split: {oos_split_pct}%\n"
        f"IS end: {is_end.strftime('%Y%m%d')}\n"
        f"OOS start: {oos_start.strftime('%Y%m%d')}\n"
        f"Gap: {gap_days} days (expected: 1 day)\n"
        f"IS timerange: {is_timerange}\n"
        f"OOS timerange: {oos_timerange}\n"
        f"\n"
        f"Expected behavior:\n"
        f"  - IS should end at oos_start - 1 day\n"
        f"  - OOS should start at oos_start\n"
        f"  - Boundary day (oos_start) should be in OOS only\n"
        f"  - No gap should exist between IS and OOS\n"
    )
    
    # Property 4: Boundary day (oos_start) is in OOS and not in IS
    boundary_day = expected_oos_start
    boundary_in_is = is_start <= boundary_day <= is_end
    boundary_in_oos = oos_start <= boundary_day <= oos_end
    
    assert not boundary_in_is, (
        f"Bug 3 detected: Boundary day is included in IS range.\n"
        f"Date range: {date_from.strftime('%Y%m%d')} to {date_to.strftime('%Y%m%d')} ({days_total} days)\n"
        f"OOS split: {oos_split_pct}%\n"
        f"Boundary day (oos_start): {boundary_day.strftime('%Y%m%d')}\n"
        f"IS range: {is_start.strftime('%Y%m%d')} to {is_end.strftime('%Y%m%d')}\n"
        f"OOS range: {oos_start.strftime('%Y%m%d')} to {oos_end.strftime('%Y%m%d')}\n"
        f"Boundary in IS: {boundary_in_is} (expected: False)\n"
        f"Boundary in OOS: {boundary_in_oos} (expected: True)\n"
        f"\n"
        f"The boundary day should be excluded from IS and included in OOS only.\n"
    )
    
    assert boundary_in_oos, (
        f"Bug 3 detected: Boundary day is NOT included in OOS range.\n"
        f"Date range: {date_from.strftime('%Y%m%d')} to {date_to.strftime('%Y%m%d')} ({days_total} days)\n"
        f"OOS split: {oos_split_pct}%\n"
        f"Boundary day (oos_start): {boundary_day.strftime('%Y%m%d')}\n"
        f"IS range: {is_start.strftime('%Y%m%d')} to {is_end.strftime('%Y%m%d')}\n"
        f"OOS range: {oos_start.strftime('%Y%m%d')} to {oos_end.strftime('%Y%m%d')}\n"
        f"Boundary in IS: {boundary_in_is} (expected: False)\n"
        f"Boundary in OOS: {boundary_in_oos} (expected: True)\n"
        f"\n"
        f"The boundary day should be included in OOS only.\n"
    )


@pytest.mark.bug_condition
def test_bug_condition_is_oos_split_simple():
    """
    **Property 1: Bug Condition** - IS/OOS Split Verification (Simple Case)
    
    A simpler, non-property-based version of the bug condition test.
    This test directly checks a specific date range to verify the split is correct.
    
    Example from design document:
    - Full range: 20240101-20240131 (31 days)
    - OOS 20%: ~6 days
    - Expected IS: 20240101-20240124 (24 days)
    - Expected OOS: 20240125-20240131 (7 days)
    - Boundary day: 20240125 (should be in OOS only)
    
    EXPECTED OUTCOME on unfixed code: MAY PASS
      The current implementation appears correct based on code review.
      
    EXPECTED OUTCOME after fix: PASS
      The split is correct with no gap and proper boundary handling.
    
    **Validates: Requirements 1.4, 1.5, 1.6, 2.5, 2.6, 2.7**
    """
    # Create config with the example from the design document
    config = _make_loop_config(
        date_from="20240101",
        date_to="20240131",
        oos_split_pct=20.0,
    )
    
    # Create LoopService and compute timeranges
    loop_service = _make_loop_service()
    is_timerange = loop_service.compute_in_sample_timerange(config)
    oos_timerange = loop_service.compute_oos_timerange(config)
    
    # Parse the timeranges
    is_start, is_end = _parse_timerange(is_timerange)
    oos_start, oos_end = _parse_timerange(oos_timerange)
    
    # Compute expected values
    date_from = datetime(2024, 1, 1)
    date_to = datetime(2024, 1, 31)
    total_days = (date_to - date_from).days  # 30 days
    oos_days = max(1, int(total_days * 20.0 / 100.0))  # 6 days
    expected_oos_start = date_to - timedelta(days=oos_days)  # 2024-01-25
    expected_is_end = expected_oos_start - timedelta(days=1)  # 2024-01-24
    
    # Document the actual behavior
    counterexample = (
        f"Date range: 20240101-20240131 (31 days total, 30 days span)\n"
        f"OOS split: 20.0%\n"
        f"OOS days: {oos_days}\n"
        f"Expected OOS start: {expected_oos_start.strftime('%Y%m%d')}\n"
        f"Expected IS end: {expected_is_end.strftime('%Y%m%d')}\n"
        f"\n"
        f"Actual IS timerange: {is_timerange}\n"
        f"Actual OOS timerange: {oos_timerange}\n"
        f"\n"
        f"Parsed IS: {is_start.strftime('%Y%m%d')} to {is_end.strftime('%Y%m%d')}\n"
        f"Parsed OOS: {oos_start.strftime('%Y%m%d')} to {oos_end.strftime('%Y%m%d')}\n"
        f"\n"
        f"Boundary day: {expected_oos_start.strftime('%Y%m%d')}\n"
        f"Boundary in IS: {is_start <= expected_oos_start <= is_end}\n"
        f"Boundary in OOS: {oos_start <= expected_oos_start <= oos_end}\n"
        f"Gap between IS and OOS: {(oos_start - is_end).days} days\n"
    )
    
    # Check all properties
    is_end_correct = is_end == expected_is_end
    oos_start_correct = oos_start == expected_oos_start
    no_gap = (oos_start - is_end).days == 1
    boundary_not_in_is = not (is_start <= expected_oos_start <= is_end)
    boundary_in_oos = oos_start <= expected_oos_start <= oos_end
    
    all_correct = (
        is_end_correct
        and oos_start_correct
        and no_gap
        and boundary_not_in_is
        and boundary_in_oos
    )
    
    if not all_correct:
        # Document which properties failed
        failures = []
        if not is_end_correct:
            failures.append(f"IS end incorrect: expected {expected_is_end.strftime('%Y%m%d')}, got {is_end.strftime('%Y%m%d')}")
        if not oos_start_correct:
            failures.append(f"OOS start incorrect: expected {expected_oos_start.strftime('%Y%m%d')}, got {oos_start.strftime('%Y%m%d')}")
        if not no_gap:
            failures.append(f"Gap between IS and OOS: {(oos_start - is_end).days} days (expected 1)")
        if not boundary_not_in_is:
            failures.append(f"Boundary day {expected_oos_start.strftime('%Y%m%d')} is in IS (should be excluded)")
        if not boundary_in_oos:
            failures.append(f"Boundary day {expected_oos_start.strftime('%Y%m%d')} is NOT in OOS (should be included)")
        
        pytest.fail(
            f"Bug 3 detected: IS/OOS split is incorrect.\n\n"
            f"{counterexample}\n"
            f"Failures:\n" + "\n".join(f"  - {f}" for f in failures) + "\n\n"
            f"This indicates Bug 3 exists: the IS/OOS split creates a gap or overlap, "
            f"or the boundary day is not handled correctly."
        )
    
    # If we reach here, all properties are correct
    # This means Bug 3 does NOT exist (current implementation is correct)
    print(
        f"\n{'='*70}\n"
        f"Bug 3 verification PASSED - Current implementation is CORRECT\n"
        f"{'='*70}\n"
        f"{counterexample}\n"
        f"All properties verified:\n"
        f"  ✓ IS ends at oos_start - 1 day\n"
        f"  ✓ OOS starts at oos_start\n"
        f"  ✓ No gap between IS and OOS (1 day difference)\n"
        f"  ✓ Boundary day excluded from IS\n"
        f"  ✓ Boundary day included in OOS\n"
        f"\n"
        f"Conclusion: Bug 3 does NOT exist. The current implementation correctly\n"
        f"handles the IS/OOS split with no gap and proper boundary day handling.\n"
        f"{'='*70}\n"
    )


@pytest.mark.bug_condition
@given(
    oos_split_pct=st.floats(min_value=5.0, max_value=50.0),
)
@h_settings(max_examples=20, deadline=None)
def test_bug_condition_is_oos_split_various_percentages(oos_split_pct):
    """
    **Property 1: Bug Condition** - IS/OOS Split with Various Percentages
    
    Test the IS/OOS split with various OOS percentage values to ensure
    the split is correct across different configurations.
    
    **Validates: Requirements 1.4, 1.5, 1.6, 2.5, 2.6, 2.7**
    """
    # Use a fixed date range for consistency
    config = _make_loop_config(
        date_from="20240101",
        date_to="20240331",  # 90 days
        oos_split_pct=oos_split_pct,
    )
    
    # Create LoopService and compute timeranges
    loop_service = _make_loop_service()
    is_timerange = loop_service.compute_in_sample_timerange(config)
    oos_timerange = loop_service.compute_oos_timerange(config)
    
    # Skip if either timerange is empty
    assume(is_timerange and oos_timerange)
    assume("-" in is_timerange and "-" in oos_timerange)
    
    # Parse the timeranges
    is_start, is_end = _parse_timerange(is_timerange)
    oos_start, oos_end = _parse_timerange(oos_timerange)
    
    # Compute expected values
    date_from = datetime(2024, 1, 1)
    date_to = datetime(2024, 3, 31)
    expected_oos_start = _compute_oos_start(date_from, date_to, oos_split_pct)
    expected_is_end = expected_oos_start - timedelta(days=1)
    
    # Verify all properties
    assert is_end == expected_is_end, (
        f"IS end incorrect for {oos_split_pct}% OOS split"
    )
    assert oos_start == expected_oos_start, (
        f"OOS start incorrect for {oos_split_pct}% OOS split"
    )
    assert (oos_start - is_end).days == 1, (
        f"Gap between IS and OOS for {oos_split_pct}% OOS split"
    )
    assert not (is_start <= expected_oos_start <= is_end), (
        f"Boundary day in IS for {oos_split_pct}% OOS split"
    )
    assert oos_start <= expected_oos_start <= oos_end, (
        f"Boundary day not in OOS for {oos_split_pct}% OOS split"
    )
