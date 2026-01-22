"""Capture screenshots with spectral class star colors."""
import asyncio
from playwright.async_api import async_playwright

async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1280, 'height': 800})
        
        import subprocess
        server = subprocess.Popen(
            ['python', '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8768'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await asyncio.sleep(3)
        
        try:
            await page.goto('http://127.0.0.1:8768', wait_until='networkidle', timeout=15000)
            await asyncio.sleep(1)
            
            await page.click('#menu-new-game')
            await asyncio.sleep(0.5)
            await page.fill('#game-name', 'Spectral Stars Test')
            await page.click('button:has-text("Create Game")')
            await asyncio.sleep(2)
            
            # Count spectral classes
            classes = await page.evaluate('''() => {
                const counts = {};
                for (const star of GameState.stars) {
                    const sc = star.spectral_class || 'G';
                    counts[sc] = (counts[sc] || 0) + 1;
                }
                return counts;
            }''')
            print(f"Spectral class distribution: {classes}")

            # Debug: check raw star data
            sample_stars = await page.evaluate('''() => {
                return GameState.stars.slice(0, 3).map(s => ({
                    name: s.name,
                    spectral_class: s.spectral_class,
                    star_temperature: s.star_temperature,
                    star_radius: s.star_radius,
                    all_keys: Object.keys(s)
                }));
            }''')
            print(f"Sample star data: {sample_stars}")
            
            # Full galaxy view
            await page.evaluate('GalaxyMap.setZoom(0.5)')
            await page.evaluate('GalaxyMap.centerOn(300, 300)')
            await asyncio.sleep(0.5)
            await page.screenshot(path='walkthrough/spectral-1-full.png')
            print("Screenshot 1: Full galaxy")
            
            # Medium zoom
            await page.evaluate('GalaxyMap.setZoom(0.8)')
            await page.evaluate('GalaxyMap.centerOnHomeworld()')
            await asyncio.sleep(0.5)
            await page.screenshot(path='walkthrough/spectral-2-medium.png')
            print("Screenshot 2: Medium zoom")
            
            # Close zoom
            await page.evaluate('GalaxyMap.setZoom(1.2)')
            await asyncio.sleep(0.5)
            await page.screenshot(path='walkthrough/spectral-3-close.png')
            print("Screenshot 3: Close zoom with star colors visible")
            
        finally:
            server.terminate()
            await browser.close()

asyncio.run(capture())
