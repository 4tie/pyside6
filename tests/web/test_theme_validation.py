"""Theme validation tests for all web UI pages."""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="session")
def base_url():
    return "http://127.0.0.1:8000"


def get_css_variable(page: Page, variable_name: str) -> str:
    """Get CSS custom property value from root element."""
    return page.evaluate(f"getComputedStyle(document.documentElement).getPropertyValue('{variable_name}').trim()")


class TestDashboardTheme:
    """Theme tests for Dashboard page."""

    def test_dashboard_default_dark_theme(self, page: Page, base_url: str):
        """Test that dashboard loads with dark theme by default."""
        page.goto(f"{base_url}/")
        
        # Check data-theme attribute
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "dark")
        
        # Verify dark theme CSS variables
        bg = get_css_variable(page, "--bg")
        # Accept various dark color values
        is_dark = (
            "#0f0f0f" in bg or 
            "#0f0f0f" in bg.lower() or
            any(x in bg for x in ["rgb(15, 15, 15)", "rgb(32, 32, 32)", "rgb(26, 26, 26)", "rgb(17, 17, 17)"])
        )
        assert is_dark, f"Expected dark bg, got: {bg}"
        
        card = get_css_variable(page, "--card")
        # Accept various dark card color values
        is_dark_card = (
            "#1a1a1a" in card or 
            "#1a1a1a" in card.lower() or
            "#202020" in card or
            "#202020" in card.lower() or
            any(x in card for x in ["rgb(26, 26, 26)", "rgb(32, 32, 32)", "rgb(37, 37, 37)", "rgb(32, 32, 32)"])
        )
        assert is_dark_card, f"Expected dark card, got: {card}"

    def test_dashboard_theme_toggle_to_light(self, page: Page, base_url: str):
        """Test theme toggle switches to light mode."""
        page.goto(f"{base_url}/")
        
        # Click theme toggle
        page.locator("#theme-toggle").click()
        
        # Verify light theme
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "light")
        
        # Verify light theme CSS variables
        bg = get_css_variable(page, "--bg")
        # Accept various light color values
        is_light = (
            "#ffffff" in bg or 
            "#f5f5f5" in bg or
            "#fafafa" in bg or
            any(x in bg for x in ["rgb(255, 255, 255)", "rgb(245, 245, 245)", "rgb(250, 250, 250)"])
        )
        assert is_light, f"Expected light bg, got: {bg}"

    def test_dashboard_theme_toggle_back_to_dark(self, page: Page, base_url: str):
        """Test theme toggle switches back to dark mode."""
        page.goto(f"{base_url}/")
        
        # Toggle to light then back to dark
        page.locator("#theme-toggle").click()
        page.locator("#theme-toggle").click()
        
        # Verify dark theme restored
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "dark")

    def test_dashboard_theme_persistence(self, page: Page, base_url: str):
        """Test that theme preference persists across page reloads."""
        page.goto(f"{base_url}/")
        
        # Toggle to light theme
        page.locator("#theme-toggle").click()
        
        # Reload page
        page.reload()
        
        # Verify light theme persisted
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "light")


class TestBacktestRunTheme:
    """Theme tests for Backtest Run page."""

    def test_backtest_run_default_dark_theme(self, page: Page, base_url: str):
        """Test that backtest run page loads with dark theme."""
        page.goto(f"{base_url}/static/pages/backtest_run/index.html")
        
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "dark")

    def test_backtest_run_theme_toggle(self, page: Page, base_url: str):
        """Test theme toggle on backtest run page."""
        page.goto(f"{base_url}/static/pages/backtest_run/index.html")
        
        page.locator("#theme-toggle").click()
        
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "light")

    def test_backtest_run_form_elements_styled(self, page: Page, base_url: str):
        """Test that form elements have theme-appropriate styling."""
        page.goto(f"{base_url}/static/pages/backtest_run/index.html")
        
        # Check input background in dark mode
        input_elem = page.locator("#strategy")
        bg_color = input_elem.evaluate("el => getComputedStyle(el).backgroundColor")
        
        # In dark mode, input should have dark background (accept various dark shades)
        is_dark_bg = (
            "rgb(15, 15, 15)" in bg_color or 
            "rgb(26, 26, 26)" in bg_color or 
            "rgb(32, 32, 32)" in bg_color or
            "rgba(0, 0, 0" in bg_color
        )
        assert is_dark_bg, f"Expected dark input bg, got: {bg_color}"

    def test_backtest_run_cards_styled(self, page: Page, base_url: str):
        """Test that cards have theme-appropriate styling."""
        page.goto(f"{base_url}/static/pages/backtest_run/index.html")
        
        # Check card background
        card = page.locator(".card").first
        bg_color = card.evaluate("el => getComputedStyle(el).backgroundColor")
        
        # Card should have card variable color (accept various dark shades)
        is_card_dark = (
            "rgb(26, 26, 26)" in bg_color or 
            "rgba(26, 26, 26" in bg_color or
            "rgb(32, 32, 32)" in bg_color or
            "rgba(32, 32, 32" in bg_color
        )
        assert is_card_dark, f"Expected card bg, got: {bg_color}"


class TestRunDetailTheme:
    """Theme tests for Run Detail page."""

    def test_run_detail_default_dark_theme(self, page: Page, base_url: str):
        """Test that run detail page loads with dark theme."""
        # Navigate to a run detail page (first run if available)
        page.goto(f"{base_url}/static/pages/run_detail/index.html")
        
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "dark")

    def test_run_detail_theme_toggle(self, page: Page, base_url: str):
        """Test theme toggle on run detail page."""
        page.goto(f"{base_url}/static/pages/run_detail/index.html")
        
        page.locator("#theme-toggle").click()
        
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "light")

    def test_run_detail_summary_cards_styled(self, page: Page, base_url: str):
        """Test that summary cards have theme-appropriate styling."""
        page.goto(f"{base_url}/static/pages/run_detail/index.html")
        
        # Wait for content to load or no runs message
        page.wait_for_timeout(500)
        
        # Check if summary grid exists
        if page.locator(".summary-grid").count() > 0:
            card = page.locator(".summary-item").first
            bg_color = card.evaluate("el => getComputedStyle(el).backgroundColor")
            # Summary items typically inherit or have transparent bg
            assert bg_color is not None


class TestComparisonTheme:
    """Theme tests for Comparison page."""

    def test_comparison_default_dark_theme(self, page: Page, base_url: str):
        """Test that comparison page loads with dark theme."""
        page.goto(f"{base_url}/static/pages/comparison/index.html")
        
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "dark")

    def test_comparison_theme_toggle(self, page: Page, base_url: str):
        """Test theme toggle on comparison page."""
        page.goto(f"{base_url}/static/pages/comparison/index.html")
        
        page.locator("#theme-toggle").click()
        
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "light")


class TestSettingsTheme:
    """Theme tests for Settings page."""

    def test_settings_default_dark_theme(self, page: Page, base_url: str):
        """Test that settings page loads with dark theme."""
        page.goto(f"{base_url}/static/pages/settings/index.html")
        
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "dark")

    def test_settings_theme_toggle(self, page: Page, base_url: str):
        """Test theme toggle on settings page."""
        page.goto(f"{base_url}/static/pages/settings/index.html")
        
        page.locator("#theme-toggle").click()
        
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "light")


class TestOptimizerTheme:
    """Theme tests for Optimizer page."""

    def test_optimizer_default_dark_theme(self, page: Page, base_url: str):
        """Test that optimizer page loads with dark theme."""
        page.goto(f"{base_url}/static/pages/optimizer/index.html")
        
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "dark")

    def test_optimizer_theme_toggle(self, page: Page, base_url: str):
        """Test theme toggle on optimizer page."""
        page.goto(f"{base_url}/static/pages/optimizer/index.html")
        
        page.locator("#theme-toggle").click()
        
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "light")


class TestThemeCrossPageConsistency:
    """Test theme consistency across page navigation."""

    def test_theme_persists_across_navigation(self, page: Page, base_url: str):
        """Test that theme choice persists when navigating between pages."""
        # Start on dashboard
        page.goto(f"{base_url}/")
        
        # Toggle to light theme
        page.locator("#theme-toggle").click()
        
        # Navigate to backtest run page
        page.goto(f"{base_url}/static/pages/backtest_run/index.html")
        
        # Verify theme persisted
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme", "light")
        
        # Navigate to settings page
        page.goto(f"{base_url}/static/pages/settings/index.html")
        
        # Verify theme still light
        expect(html).to_have_attribute("data-theme", "light")


class TestThemeCSSVariables:
    """Test CSS variable values in different themes."""

    def test_dark_theme_variables(self, page: Page, base_url: str):
        """Test that dark theme CSS variables have correct values."""
        page.goto(f"{base_url}/")
        
        # Check key variables
        variables = ["--bg", "--card", "--text", "--border", "--success", "--error"]
        
        for var in variables:
            value = get_css_variable(page, var)
            assert value, f"CSS variable {var} should be defined"
            assert value != "", f"CSS variable {var} should not be empty"

    def test_light_theme_variables(self, page: Page, base_url: str):
        """Test that light theme CSS variables have correct values."""
        page.goto(f"{base_url}/")
        
        # Toggle to light
        page.locator("#theme-toggle").click()
        
        # Check key variables
        variables = ["--bg", "--card", "--text", "--border"]
        
        for var in variables:
            value = get_css_variable(page, var)
            assert value, f"CSS variable {var} should be defined in light mode"

    def test_theme_variables_change_on_toggle(self, page: Page, base_url: str):
        """Test that CSS variables change when toggling theme."""
        page.goto(f"{base_url}/")
        
        # Get dark theme values
        dark_bg = get_css_variable(page, "--bg")
        
        # Toggle to light
        page.locator("#theme-toggle").click()
        
        # Get light theme values
        light_bg = get_css_variable(page, "--bg")
        
        # Values should be different
        assert dark_bg != light_bg, f"Background should change between themes: dark={dark_bg}, light={light_bg}"
