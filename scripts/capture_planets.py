#!/usr/bin/env python3
"""
Capture screenshots of procedurally generated planets with various characteristics.
Shows range of planet types from frozen to scorching, low to high radiation/gravity.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from playwright.async_api import async_playwright

OUTPUT_DIR = project_root / "walkthrough" / "planets"
BASE_URL = "http://localhost:9800"


# Planet configurations to capture
PLANET_CONFIGS = [
    # (name, temperature, radiation, gravity, description)
    ("frozen_low_rad", 10, 15, 50, "Frozen world, low radiation"),
    ("frozen_high_rad", 10, 85, 50, "Frozen world, high radiation"),
    ("cold_earthlike", 35, 40, 50, "Cold but habitable"),
    ("temperate_ideal", 50, 50, 50, "Temperate ideal world"),
    ("temperate_low_grav", 50, 50, 20, "Temperate, low gravity (small)"),
    ("temperate_high_grav", 50, 50, 80, "Temperate, high gravity (large)"),
    ("temperate_high_rad", 50, 90, 50, "Temperate, high radiation"),
    ("hot_desert", 70, 30, 50, "Hot desert world"),
    ("hot_volcanic", 75, 70, 60, "Hot volcanic world"),
    ("scorching_hell", 95, 95, 70, "Scorching hellworld"),
    ("gas_giant_cold", 25, 40, 95, "Cold gas giant"),
    ("gas_giant_hot", 80, 60, 95, "Hot gas giant"),
]


async def wait_for_app(page):
    """Wait for app to initialize."""
    await page.wait_for_selector("#menu-bar", timeout=10000)
    await page.wait_for_function("typeof window.App !== 'undefined'")
    await asyncio.sleep(0.5)


async def create_game(page):
    """Create a new game."""
    await page.click("#menu-new-game")
    await page.wait_for_selector("#dialog-overlay:not(.hidden)", timeout=5000)
    await asyncio.sleep(0.3)

    game_name = await page.query_selector("#game-name")
    if game_name:
        await game_name.fill("Planet Screenshots")

    create_btn = await page.query_selector("#btn-create-game")
    if create_btn:
        await create_btn.click()

    await asyncio.sleep(2)
    await page.wait_for_selector("#game-container:not(.hidden)", timeout=15000)
    await asyncio.sleep(0.5)


async def capture_planet(page, config, index):
    """Capture a single planet with specific characteristics."""
    name, temp, rad, grav, desc = config

    # Use JavaScript to modify a star's properties and re-render
    await page.evaluate(f'''() => {{
        // Find homeworld star
        const star = GameState.stars.find(s => s.name === GameState.homeworldName) || GameState.stars[0];
        if (!star) return;

        // Modify environmental values
        star.temperature = {temp};
        star.radiation = {rad};
        star.gravity = {grav};
        star.habitability = undefined;  // Force recalculation

        // Re-render the star panel
        if (typeof StarPanel !== 'undefined') {{
            StarPanel.show(star);
        }}
    }}''')

    await asyncio.sleep(0.3)

    # Get just the planet canvas area
    planet_display = await page.query_selector(".planet-display")
    if planet_display:
        filename = f"{index:02d}_{name}.png"
        await planet_display.screenshot(path=str(OUTPUT_DIR / filename))
        print(f"  - {filename} ({desc})")
        return True

    return False


async def capture_full_panel(page, config, index):
    """Capture full star panel with planet."""
    name, temp, rad, grav, desc = config

    # Modify star and re-render
    await page.evaluate(f'''() => {{
        const star = GameState.stars.find(s => s.name === GameState.homeworldName) || GameState.stars[0];
        if (!star) return;

        star.temperature = {temp};
        star.radiation = {rad};
        star.gravity = {grav};
        star.habitability = undefined;

        if (typeof StarPanel !== 'undefined') {{
            StarPanel.show(star);
        }}
    }}''')

    await asyncio.sleep(0.3)

    # Capture full panel
    star_panel = await page.query_selector("#star-panel")
    if star_panel:
        filename = f"{index:02d}_{name}_panel.png"
        await star_panel.screenshot(path=str(OUTPUT_DIR / filename))
        print(f"  - {filename} (full panel)")
        return True

    return False


async def main():
    """Main capture function."""
    print("=" * 60)
    print("Planet Screenshot Generator")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        await page.goto(BASE_URL)
        await wait_for_app(page)

        print("\nCreating game...")
        await create_game(page)

        # Click on homeworld to show star panel
        await page.evaluate('''() => {
            const star = GameState.stars.find(s => s.name === GameState.homeworldName);
            if (star && typeof StarPanel !== 'undefined') {
                StarPanel.show(star);
            }
        }''')
        await asyncio.sleep(0.5)

        print("\nCapturing planet variations...")
        for i, config in enumerate(PLANET_CONFIGS, start=1):
            await capture_planet(page, config, i)

        print("\nCapturing full panels for key types...")
        key_types = [
            ("frozen_panel", 10, 15, 50, "Frozen"),
            ("temperate_panel", 50, 50, 50, "Temperate"),
            ("scorching_panel", 95, 95, 70, "Scorching"),
        ]
        for i, config in enumerate(key_types, start=20):
            await capture_full_panel(page, config, i)

        await context.close()
        await browser.close()

    print("=" * 60)
    print("Complete!")

    files = sorted(OUTPUT_DIR.glob("*.png"))
    print(f"\nGenerated {len(files)} screenshots:")
    for f in files:
        print(f"  - {f.name}")


if __name__ == "__main__":
    asyncio.run(main())
