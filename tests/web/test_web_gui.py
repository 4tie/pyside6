"""Playwright tests for web GUI validation."""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="session")
def base_url():
    return "http://127.0.0.1:8000"


def test_dashboard_loads(page: Page, base_url: str):
    """Test that dashboard page loads correctly."""
    page.goto(f"{base_url}/static/pages/dashboard/index.html")
    
    # Check page title
    expect(page).to_have_title("Dashboard - PySide6 Freqtrade")
    
    # Check navbar is present
    expect(page.locator(".navbar")).to_be_visible()
    
    # Check navigation links
    expect(page.locator('.navbar-links a[href="/static/pages/dashboard/index.html"]')).to_be_visible()
    expect(page.locator('.navbar-links a[href="/static/pages/backtest_run/index.html"]')).to_be_visible()
    expect(page.locator('.navbar-links a[href="/static/pages/run_detail/index.html"]')).to_be_visible()
    expect(page.locator('.navbar-links a[href="/static/pages/comparison/index.html"]')).to_be_visible()
    expect(page.locator('.navbar-links a[href="/static/pages/settings/index.html"]')).to_be_visible()


def test_backtest_run_page_loads(page: Page, base_url: str):
    """Test that backtest run page loads correctly."""
    page.goto(f"{base_url}/static/pages/backtest_run/index.html")
    
    # Check page title
    expect(page).to_have_title("Run Backtest - PySide6 Freqtrade")
    
    # Check navbar is present
    expect(page.locator(".navbar")).to_be_visible()
    
    # Check form is present
    expect(page.locator("#backtest-form")).to_be_visible()
    
    # Check form fields
    expect(page.locator("#strategy")).to_be_visible()
    expect(page.locator("#timeframe")).to_be_visible()
    expect(page.locator("#timerange")).to_be_visible()
    expect(page.locator("#pairs-search")).to_be_visible()
    expect(page.locator("#max_open_trades")).to_be_visible()
    expect(page.locator("#dry_run_wallet")).to_be_visible()
    
    # Check buttons
    expect(page.locator("#download-data-btn")).to_be_visible()
    expect(page.locator("#run-backtest-btn")).to_be_visible()
    
    # Check logs panel
    expect(page.locator(".logs-panel")).to_be_visible()


def test_backtest_run_navigation_active(page: Page, base_url: str):
    """Test that Run Backtest link is active on backtest run page."""
    page.goto(f"{base_url}/static/pages/backtest_run/index.html")
    
    # Check that Run Backtest link has active class
    expect(page.locator('.navbar-links a[href="/static/pages/backtest_run/index.html"]')).to_have_class("active")


def test_backtest_run_theme_toggle(page: Page, base_url: str):
    """Test that theme toggle button works."""
    page.goto(f"{base_url}/static/pages/backtest_run/index.html")
    
    # Check theme toggle button is present
    theme_toggle = page.locator("#theme-toggle")
    expect(theme_toggle).to_be_visible()
    
    # Click theme toggle
    theme_toggle.click()
    
    # Check that theme changed (data-theme attribute should be present)
    # Note: This is a basic check, actual theme verification would need more detailed checks
    html = page.locator("html")
    expect(html).to_have_attribute("data-theme", "light")


def test_backtest_run_pairs_container(page: Page, base_url: str):
    """Test that pairs container loads correctly."""
    page.goto(f"{base_url}/static/pages/backtest_run/index.html")
    
    # Wait for pairs to load
    page.wait_for_selector("#pairs-container", timeout=5000)
    
    # Check pairs container is visible
    expect(page.locator("#pairs-container")).to_be_visible()
    
    # Check randomize pairs button
    expect(page.locator("#randomize-pairs")).to_be_visible()


def test_dashboard_navigation_links(page: Page, base_url: str):
    """Test that navigation links work correctly from dashboard."""
    page.goto(f"{base_url}/static/pages/dashboard/index.html")
    
    # Click Run Backtest link
    page.locator('a[href="/static/pages/backtest_run/index.html"]').click()
    
    # Should navigate to backtest run page
    expect(page).to_have_url(f"{base_url}/static/pages/backtest_run/index.html")
    
    # Check page title
    expect(page).to_have_title("Run Backtest - PySide6 Freqtrade")
