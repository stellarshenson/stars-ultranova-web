#!/usr/bin/env python3
"""
Capture screenshots of Stars Nova Web UI features using Playwright.
Generates screenshots for menu system, panels, reports, and layout.

Screenshot Organization:
- 01-02: Main menu screen (before game starts)
- 03-08: Menu bar dropdowns (all 6 menus)
- 09-10: Game layout and panels
- 11-13: Reports dialog tabs
- 14-17: View toggles and zoom
- 18-20: Other features (designer, settings, about)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from playwright.async_api import async_playwright


OUTPUT_DIR = project_root / "walkthrough" / "ui_redesign"
BASE_URL = "http://localhost:9800"


async def wait_for_app(page):
    """Wait for the app to initialize."""
    await page.wait_for_selector("#menu-bar", timeout=10000)
    await page.wait_for_function("typeof window.App !== 'undefined'")
    await asyncio.sleep(0.5)


async def create_game(page):
    """Create a new game to enable game UI."""
    # Click New Game button
    await page.click("#menu-new-game")
    await page.wait_for_selector("#dialog-overlay:not(.hidden)", timeout=5000)
    await asyncio.sleep(0.3)

    # Fill in game name
    game_name_input = await page.query_selector("#game-name")
    if game_name_input:
        await game_name_input.fill("Screenshot Demo")

    # Click Create button - use the correct ID from dialogs.js
    create_btn = await page.query_selector("#btn-create-game")
    if create_btn:
        await create_btn.click()
    else:
        print("  WARNING: Create button not found")
        return False

    # Wait longer for API call to complete and game to load
    await asyncio.sleep(2)

    # Wait for game container to be visible
    try:
        await page.wait_for_selector("#game-container:not(.hidden)", timeout=15000)
        await asyncio.sleep(0.5)
        return True
    except Exception as e:
        print(f"  WARNING: Game container not visible: {e}")
        # Take a debug screenshot
        await page.screenshot(path=str(OUTPUT_DIR / "debug_create_game.png"))
        return False


async def capture_main_menu_screen(page, browser):
    """Capture main menu screen (before game starts)."""
    print("Capturing main menu screen...")

    # Fresh page for main menu
    context = await browser.new_context(viewport={"width": 1400, "height": 900})
    page = await context.new_page()
    await page.goto(BASE_URL)
    await wait_for_app(page)

    # Main menu screen - shows title card with buttons
    await page.screenshot(path=str(OUTPUT_DIR / "01_main_menu.png"))
    print("  - 01_main_menu.png")

    # New Game dialog
    await page.click("#menu-new-game")
    await page.wait_for_selector("#dialog-overlay:not(.hidden)", timeout=5000)
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(OUTPUT_DIR / "02_new_game_dialog.png"))
    print("  - 02_new_game_dialog.png")

    await context.close()


async def capture_menu_dropdowns(page):
    """Capture all 6 menu bar dropdowns."""
    print("Capturing menu bar dropdowns...")

    menus = [
        ("file", "File menu - game management"),
        ("view", "View menu - display toggles"),
        ("turn", "Turn menu - turn generation"),
        ("commands", "Commands menu - fleet/ship actions"),
        ("report", "Report menu - summaries"),
        ("help", "Help menu - documentation")
    ]

    for i, (menu_id, desc) in enumerate(menus, start=3):
        # Click to open menu
        await page.click(f".menu-item[data-menu='{menu_id}']")
        await asyncio.sleep(0.3)

        # Take screenshot
        filename = f"{i:02d}_menu_{menu_id}.png"
        await page.screenshot(path=str(OUTPUT_DIR / filename))
        print(f"  - {filename} ({desc})")

        # Close menu by clicking elsewhere
        await page.click("#scanner-pane")
        await asyncio.sleep(0.2)


async def capture_game_layout(page):
    """Capture game layout screenshots."""
    print("Capturing game layout...")

    # Full game layout - shows 40/60 split
    await page.screenshot(path=str(OUTPUT_DIR / "09_game_layout.png"))
    print("  - 09_game_layout.png (40/60 split layout)")

    # Click on canvas to potentially select a star
    canvas = await page.query_selector("#galaxy-map")
    if canvas:
        box = await canvas.bounding_box()
        if box:
            # Click near center where homeworld should be
            await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            await asyncio.sleep(0.5)

    # Check if star panel is now visible
    star_panel = await page.query_selector("#star-panel:not(.hidden)")
    if star_panel:
        await page.screenshot(path=str(OUTPUT_DIR / "10_star_panel.png"))
        print("  - 10_star_panel.png (star/planet info panel)")
    else:
        # Just take the layout shot anyway
        await page.screenshot(path=str(OUTPUT_DIR / "10_layout_with_selection.png"))
        print("  - 10_layout_with_selection.png")


async def capture_reports(page):
    """Capture reports dialog with all tabs."""
    print("Capturing reports dialog...")

    # Open Reports via menu
    await page.click(".menu-item[data-menu='report']")
    await asyncio.sleep(0.2)
    await page.click(".menu-action[data-action='planetSummary']")
    await asyncio.sleep(0.5)

    # Check if reports panel is visible
    reports = await page.query_selector("#reports-panel:not(.hidden)")
    if reports:
        # Planet report tab
        await page.screenshot(path=str(OUTPUT_DIR / "11_report_planets.png"))
        print("  - 11_report_planets.png (planet summary)")

        # Fleet report tab - use .report-tab not .reports-tab
        fleet_tab = await page.query_selector(".report-tab[data-tab='fleets']")
        if fleet_tab:
            await fleet_tab.click()
            await asyncio.sleep(0.3)
            await page.screenshot(path=str(OUTPUT_DIR / "12_report_fleets.png"))
            print("  - 12_report_fleets.png (fleet summary)")
        else:
            print("  - Fleet tab not found")

        # Research report tab
        research_tab = await page.query_selector(".report-tab[data-tab='research']")
        if research_tab:
            await research_tab.click()
            await asyncio.sleep(0.3)
            await page.screenshot(path=str(OUTPUT_DIR / "13_report_research.png"))
            print("  - 13_report_research.png (research status)")
        else:
            print("  - Research tab not found")

        # Close reports - use the btn-close button inside reports panel
        close_btn = await page.query_selector("#reports-panel .btn-close")
        if close_btn:
            await close_btn.click()
            await asyncio.sleep(0.5)
        else:
            # Fallback: try pressing Escape
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
    else:
        print("  - Reports panel not found, skipping")


async def capture_view_features(page):
    """Capture view toggles and zoom features using keyboard shortcuts."""
    print("Capturing view features...")

    # Focus on the map area first
    await page.click("#scanner-pane")
    await asyncio.sleep(0.3)

    # Toggle scanner range on using Shift+S
    await page.keyboard.press("Shift+S")
    await asyncio.sleep(0.5)
    await page.screenshot(path=str(OUTPUT_DIR / "14_scanner_range.png"))
    print("  - 14_scanner_range.png (scanner range overlay)")

    # Toggle star names off using N key
    await page.keyboard.press("n")
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(OUTPUT_DIR / "15_names_off.png"))
    print("  - 15_names_off.png (star names hidden)")

    # Toggle names back on
    await page.keyboard.press("n")
    await asyncio.sleep(0.3)

    # Zoom in twice using + key
    await page.keyboard.press("+")
    await asyncio.sleep(0.3)
    await page.keyboard.press("+")
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(OUTPUT_DIR / "16_zoomed_in.png"))
    print("  - 16_zoomed_in.png (zoomed in view)")

    # Zoom to fit using Home key
    await page.keyboard.press("Home")
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(OUTPUT_DIR / "17_zoom_fit.png"))
    print("  - 17_zoom_fit.png (zoom to fit)")

    # Turn off scanner range for cleaner later screenshots
    await page.keyboard.press("Shift+S")
    await asyncio.sleep(0.3)


async def capture_ship_designer(page):
    """Capture ship designer panel."""
    print("Capturing ship designer...")

    # Open via menu
    await page.click(".menu-item[data-menu='commands']")
    await asyncio.sleep(0.2)
    await page.click(".menu-action[data-action='designShip']")
    await asyncio.sleep(0.5)

    # Check if design panel is visible
    design_panel = await page.query_selector("#design-panel:not(.hidden)")
    if design_panel:
        await page.screenshot(path=str(OUTPUT_DIR / "18_ship_designer.png"))
        print("  - 18_ship_designer.png (ship designer)")

        # Close it
        close_btn = await page.query_selector("#design-panel .panel-close, #design-panel .close-btn")
        if close_btn:
            await close_btn.click()
            await asyncio.sleep(0.3)
    else:
        print("  - Ship designer not available")


async def capture_settings(page):
    """Capture settings dialog from main menu."""
    print("Capturing settings...")

    # Settings button is on main menu card - check if visible
    settings_btn = await page.query_selector("#menu-settings")
    if settings_btn:
        # Need to close game first? Check if menu-container is visible
        menu_container = await page.query_selector("#menu-container:not(.hidden)")
        if not menu_container:
            # Game is active, try via File menu
            await page.click(".menu-item[data-menu='file']")
            await asyncio.sleep(0.2)
            # Check for settings item
            settings_item = await page.query_selector(".menu-action[data-action='settings']")
            if settings_item:
                await settings_item.click()
            else:
                print("  - No settings in File menu")
                return
        else:
            await settings_btn.click()

        try:
            await page.wait_for_selector("#dialog-overlay:not(.hidden)", timeout=3000)
            await asyncio.sleep(0.3)
            await page.screenshot(path=str(OUTPUT_DIR / "19_settings.png"))
            print("  - 19_settings.png (settings dialog)")

            # Close dialog
            close_btn = await page.query_selector(".btn-close")
            if close_btn:
                await close_btn.click()
                await asyncio.sleep(0.2)
        except:
            print("  - Settings dialog not available")


async def capture_about(page):
    """Capture about dialog."""
    print("Capturing about dialog...")

    # Open Help menu and click About
    try:
        await page.click(".menu-item[data-menu='help']")
        await asyncio.sleep(0.4)
        await page.click(".menu-action[data-action='about']")
        await asyncio.sleep(0.5)
    except Exception as e:
        print(f"  - Could not open Help menu: {e}")
        return

    # Check for dialog
    dialog = await page.query_selector("#dialog-overlay:not(.hidden)")
    if dialog:
        await page.screenshot(path=str(OUTPUT_DIR / "20_about.png"))
        print("  - 20_about.png (about dialog)")

        # Close by pressing Escape
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.2)
    else:
        print("  - About dialog not available")


async def main():
    """Main screenshot capture function."""
    print("=" * 60)
    print("Stars Nova Web - UI Screenshot Capture")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Part 1: Main menu screen (before game is created)
        await capture_main_menu_screen(None, browser)

        # Part 2: Create a game and capture game UI features
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        await page.goto(BASE_URL)
        await wait_for_app(page)

        # Create a game to enable game UI
        print("\nCreating game for UI screenshots...")
        game_created = await create_game(page)

        if not game_created:
            print("WARNING: Game creation may have failed. Continuing anyway...")

        # Capture all game UI features
        await capture_menu_dropdowns(page)
        await capture_game_layout(page)
        await capture_reports(page)
        await capture_view_features(page)
        await capture_ship_designer(page)
        await capture_settings(page)
        await capture_about(page)

        await context.close()
        await browser.close()

    print("=" * 60)
    print("Screenshot capture complete!")

    # List generated files
    files = sorted(OUTPUT_DIR.glob("*.png"))
    print(f"\nGenerated {len(files)} screenshots:")
    for f in files:
        print(f"  - {f.name}")


if __name__ == "__main__":
    asyncio.run(main())
