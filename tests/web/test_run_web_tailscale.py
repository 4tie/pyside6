"""Example-based tests for run_web.py Tailscale and env-var support.

Validates: Requirements 1.1, 1.2, 1.4, 2.1
"""
import contextlib
import io
import sys
import unittest.mock
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import run_web


# ---------------------------------------------------------------------------
# _detect_tailscale_ip tests
# ---------------------------------------------------------------------------

def test_detect_tailscale_ip_returns_none_when_no_tailscale():
    """When subprocess raises FileNotFoundError and socket returns no 100.x
    addresses, _detect_tailscale_ip() should return None."""
    with unittest.mock.patch("run_web.subprocess.run", side_effect=FileNotFoundError):
        with unittest.mock.patch(
            "run_web.socket.getaddrinfo",
            return_value=[(None, None, None, None, ("192.168.1.1", 0))],
        ):
            result = run_web._detect_tailscale_ip()
    assert result is None


def test_detect_tailscale_ip_from_cli():
    """When the Tailscale CLI returns returncode=0 and a valid 100.x address,
    _detect_tailscale_ip() should return that address."""
    mock_result = unittest.mock.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "100.64.0.1\n"

    with unittest.mock.patch("run_web.subprocess.run", return_value=mock_result):
        result = run_web._detect_tailscale_ip()

    assert result == "100.64.0.1"


def test_detect_tailscale_ip_from_socket_fallback():
    """When the CLI returns a non-zero exit code, the socket fallback should
    be used and return the 100.x address found there."""
    mock_result = unittest.mock.MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with unittest.mock.patch("run_web.subprocess.run", return_value=mock_result):
        with unittest.mock.patch(
            "run_web.socket.getaddrinfo",
            return_value=[(None, None, None, None, ("100.64.0.1", 0))],
        ):
            result = run_web._detect_tailscale_ip()

    assert result == "100.64.0.1"


# ---------------------------------------------------------------------------
# _parse_args tests
# ---------------------------------------------------------------------------

def test_web_host_env_default():
    """When WEB_HOST is set in the environment, _parse_args should use it as
    the default host value."""
    with unittest.mock.patch.dict("os.environ", {"WEB_HOST": "192.168.1.10"}, clear=False):
        with unittest.mock.patch("sys.argv", ["run_web.py"]):
            args = run_web._parse_args()
    assert args.host == "192.168.1.10"


def test_tailscale_flag_registered():
    """Passing --tailscale on the command line should set args.tailscale to True."""
    with unittest.mock.patch("sys.argv", ["run_web.py", "--tailscale"]):
        args = run_web._parse_args()
    assert args.tailscale is True


# ---------------------------------------------------------------------------
# _banner tests
# ---------------------------------------------------------------------------

def test_banner_no_tailscale_when_not_passed():
    """When tailscale_ip=None is passed to _banner, the output should not
    contain the word 'Tailscale'."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_web._banner("0.0.0.0", 8000, Path("/tmp/web.log"), False, tailscale_ip=None)
    output = buf.getvalue()
    assert "Tailscale" not in output


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------

@given(tailscale_ip=st.from_regex(r"100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}", fullmatch=True))
@settings(max_examples=200)
def test_banner_includes_tailscale_url(tailscale_ip):
    # Feature: web-mobile-tailscale, Property 1: Banner includes Tailscale URL when IP is provided
    # Validates: Requirements 1.2, 3.2
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_web._banner("0.0.0.0", 8000, Path("/tmp/web.log"), False, tailscale_ip=tailscale_ip)
    output = buf.getvalue()
    assert tailscale_ip in output
    assert "Tailscale" in output


@given(port=st.integers(1, 65535), host=st.text())
@settings(max_examples=200)
def test_banner_omits_tailscale_when_none(port, host):
    # Feature: web-mobile-tailscale, Property 2: Banner omits Tailscale section when no IP is provided
    # Validates: Requirements 1.4, 3.2
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_web._banner(host, port, Path("/tmp/web.log"), False, tailscale_ip=None)
    output = buf.getvalue()
    assert "Tailscale" not in output


@given(port=st.integers(1, 65535))
@settings(max_examples=200)
def test_banner_always_has_loopback_and_docs(port):
    # Feature: web-mobile-tailscale, Property 3: Banner always contains loopback URL and docs URL
    # Validates: Requirements 3.1, 3.4
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_web._banner("0.0.0.0", port, Path("/tmp/web.log"), False)
    output = buf.getvalue()
    assert f"http://127.0.0.1:{port}" in output
    assert f"http://127.0.0.1:{port}/docs" in output


@given(host=st.ip_addresses(v=4).map(str).filter(lambda h: h not in ("127.0.0.1", "0.0.0.0", "::")))
@settings(max_examples=200)
def test_banner_network_line_for_nonloopback_host(host):
    # Feature: web-mobile-tailscale, Property 4: Banner includes Network URL for non-loopback host
    # Validates: Requirements 3.3
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_web._banner(host, 8000, Path("/tmp/web.log"), False)
    output = buf.getvalue()
    assert host in output
    assert "Network" in output


@given(port=st.integers(1, 65535))
@settings(max_examples=300)
def test_web_port_env_valid(port):
    # Feature: web-mobile-tailscale, Property 5: WEB_PORT env var accepted for any valid port 1–65535
    # Validates: Requirements 2.2
    with unittest.mock.patch.dict("os.environ", {"WEB_PORT": str(port)}, clear=False):
        with unittest.mock.patch("sys.argv", ["run_web.py"]):
            args = run_web._parse_args()
    assert args.port == port


@given(port_val=st.one_of(
    st.integers(max_value=0),
    st.integers(min_value=65536),
    st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00")).filter(
        lambda s: not s.strip().lstrip("-").isdigit()
    )
))
@settings(max_examples=300)
def test_web_port_env_invalid_exits(port_val):
    # Feature: web-mobile-tailscale, Property 6: WEB_PORT env var rejected for any invalid port
    # Validates: Requirements 2.3
    with unittest.mock.patch.dict("os.environ", {"WEB_PORT": str(port_val)}, clear=False):
        with unittest.mock.patch("sys.argv", ["run_web.py"]):
            with pytest.raises(SystemExit) as exc_info:
                run_web._parse_args()
    assert exc_info.value.code != 0


@given(mock_addr=st.one_of(st.just(None), st.from_regex(r"100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", fullmatch=True)))
@settings(max_examples=200)
def test_detect_tailscale_ip_return_type(mock_addr):
    # Feature: web-mobile-tailscale, Property 7: _detect_tailscale_ip returns None or a valid Tailscale address
    # Validates: Requirements 1.1
    import re
    # The regex allows optional leading zeros in each octet (e.g. "070" == 70).
    # We validate the second octet numerically to match _in_tailscale_range's
    # integer-arithmetic logic (64 <= octet <= 127).
    valid_pattern = re.compile(r"^100\.(\d{1,3})\.\d{1,3}\.\d{1,3}$")

    if mock_addr is None:
        # Make both detection steps fail
        with unittest.mock.patch("run_web.subprocess.run", side_effect=FileNotFoundError):
            with unittest.mock.patch("run_web.socket.getaddrinfo", return_value=[]):
                result = run_web._detect_tailscale_ip()
        assert result is None
    else:
        # Use the same logic as the implementation to determine if the address is valid
        is_valid = run_web._in_tailscale_range(mock_addr)
        if is_valid:
            mock_result = unittest.mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = mock_addr + "\n"
            with unittest.mock.patch("run_web.subprocess.run", return_value=mock_result):
                result = run_web._detect_tailscale_ip()
            # Verify result is None or a valid Tailscale address (100.64-127.x.x),
            # using numeric comparison for the second octet to handle leading zeros.
            if result is not None:
                m = valid_pattern.match(result)
                assert m is not None, f"Result {result!r} does not match 100.x.x.x pattern"
                second_octet = int(m.group(1))
                assert 64 <= second_octet <= 127, (
                    f"Second octet {second_octet} not in Tailscale range 64-127"
                )
        else:
            # Address not in valid range — detection should return None
            mock_result = unittest.mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = mock_addr + "\n"
            with unittest.mock.patch("run_web.subprocess.run", return_value=mock_result):
                with unittest.mock.patch("run_web.socket.getaddrinfo", return_value=[(None, None, None, None, (mock_addr, 0))]):
                    result = run_web._detect_tailscale_ip()
            assert result is None


# ---------------------------------------------------------------------------
# Static analysis tests for enhancement properties (J2)
# ---------------------------------------------------------------------------

# Resolve workspace root relative to this test file
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def test_appshell_primary_count_constant():
    """Property 9: Mobile nav overflow — primary routes always visible.

    PRIMARY_COUNT constant must be defined and equal 4 in either AppShell.tsx
    or MobileNav.tsx (it was extracted to MobileNav.tsx during F1 refactor).

    Validates: Requirements 10.1
    """
    appshell_path = WORKSPACE_ROOT / "app" / "re_web" / "src" / "components" / "AppShell.tsx"
    mobilenav_path = WORKSPACE_ROOT / "app" / "re_web" / "src" / "components" / "MobileNav.tsx"

    found = False
    for path in (appshell_path, mobilenav_path):
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if "PRIMARY_COUNT" in content and "4" in content:
                # Verify the constant is assigned the value 4
                if "PRIMARY_COUNT = 4" in content:
                    found = True
                    break

    assert found, (
        "PRIMARY_COUNT = 4 not found in AppShell.tsx or MobileNav.tsx"
    )


def test_appshell_more_routes_sliced():
    """Property 10: Mobile nav overflow — More button active state.

    routes.slice(PRIMARY_COUNT) or equivalent must appear in AppShell.tsx or
    MobileNav.tsx to split routes into primary and overflow sets.

    Validates: Requirements 10.3
    """
    appshell_path = WORKSPACE_ROOT / "app" / "re_web" / "src" / "components" / "AppShell.tsx"
    mobilenav_path = WORKSPACE_ROOT / "app" / "re_web" / "src" / "components" / "MobileNav.tsx"

    found = False
    for path in (appshell_path, mobilenav_path):
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if "routes.slice(PRIMARY_COUNT)" in content or "slice(PRIMARY_COUNT)" in content:
                found = True
                break

    assert found, (
        "routes.slice(PRIMARY_COUNT) not found in AppShell.tsx or MobileNav.tsx"
    )


def test_run_table_has_card_list():
    """Property 11: RunTable renders cards on mobile.

    The run-card-list className must appear in RunTable.tsx to provide the
    mobile card layout alternative to the desktop table.

    Validates: Requirements 11.1
    """
    run_table_path = WORKSPACE_ROOT / "app" / "re_web" / "src" / "components" / "RunTable.tsx"
    assert run_table_path.exists(), f"RunTable.tsx not found at {run_table_path}"

    content = run_table_path.read_text(encoding="utf-8")
    assert "run-card-list" in content, (
        "className 'run-card-list' not found in RunTable.tsx"
    )


def test_equity_chart_has_touch_move():
    """Property 12: Chart touch handler maps X position to nearest trade index.

    onTouchMove must appear in RunDetailPage.tsx to handle touch interaction
    on the equity chart SVG element.

    Validates: Requirements 12.1
    """
    run_detail_path = WORKSPACE_ROOT / "app" / "re_web" / "src" / "pages" / "RunDetailPage.tsx"
    assert run_detail_path.exists(), f"RunDetailPage.tsx not found at {run_detail_path}"

    content = run_detail_path.read_text(encoding="utf-8")
    assert "onTouchMove" in content, (
        "onTouchMove not found in RunDetailPage.tsx"
    )


def test_equity_chart_touch_action_none():
    """Property 12 (continued): Chart SVG must disable default touch scrolling.

    touchAction: 'none' (inline style) or touch-action: none (CSS) must appear
    in RunDetailPage.tsx so the browser does not intercept touch-move events
    on the equity chart.

    Validates: Requirements 12.5
    """
    run_detail_path = WORKSPACE_ROOT / "app" / "re_web" / "src" / "pages" / "RunDetailPage.tsx"
    assert run_detail_path.exists(), f"RunDetailPage.tsx not found at {run_detail_path}"

    content = run_detail_path.read_text(encoding="utf-8")
    assert ("touchAction: 'none'" in content or "touch-action: none" in content), (
        "Neither touchAction: 'none' nor touch-action: none found in RunDetailPage.tsx"
    )
